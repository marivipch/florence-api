import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pymysql

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

def get_db():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", 17257)),
        cursorclass=pymysql.cursors.DictCursor,
        ssl={"ssl_mode": "REQUIRED"}  
    )
class MedicoAnidado(BaseModel):
    codigoRegistro: int
    nombre: str
    especialidad: str

class ConsultaCreate(BaseModel):
    id: int = 0
    motivoConsulta: str
    diagnostico: str
    fechaConsulta: str
    temp: float
    fc: int
    fr: int
    medico: MedicoAnidado

class PacienteCompleto(BaseModel):
    uid: str
    nombre: str
    rh: str
    edad: int
    religion: str
    contEmergencia: int
    antPersonales: str
    antAlergicos: str
    consultas: List[ConsultaCreate] = []


@app.get("/pacientes/{uid}")
def obtener_paciente(uid: str):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT uid, nombre, rh, edad, religion, 
                   cont_emergencia AS contEmergencia, 
                   ant_personales AS antPersonales, 
                   ant_alergicos AS antAlergicos 
            FROM paciente WHERE UPPER(uid) = UPPER(%s);
        """, (uid,))
        paciente = cursor.fetchone()
        
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        
        cursor.execute("""
            SELECT cm.id, cm.motivo_consulta AS motivoConsulta, cm.diagnostico, 
                   cm.fecha_consulta AS fechaConsulta, cm.temperatura AS temp, 
                   cm.frecuencia_cardiaca AS fc, cm.frecuencia_respiratoria AS fr,
                   m.codigo_registro AS codigoRegistro, m.nombre, m.especialidad
            FROM consulta_medica cm
            JOIN medico m ON cm.codigo_registro_medico = m.codigo_registro
            WHERE UPPER(cm.uid_paciente) = UPPER(%s);
        """, (uid,))
        
        consultas_raw = cursor.fetchall()
        
        consultas_formateadas = []
        for c in consultas_raw:
            consultas_formateadas.append({
                "id": c["id"],
                "motivoConsulta": c["motivoConsulta"],
                "diagnostico": c["diagnostico"],
                "fechaConsulta": str(c["fechaConsulta"]),
                "temp": c["temp"],
                "fc": c["fc"],
                "fr": c["fr"],
                "medico": {
                    "codigoRegistro": c["codigoRegistro"],
                    "nombre": c["nombre"],
                    "especialidad": c["especialidad"]
                }
            })
            
        paciente["consultas"] = consultas_formateadas
        return paciente
    db.close()

@app.post("/pacientes")
def crear_paciente(p: PacienteCompleto):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO paciente (uid, nombre, rh, edad, religion, cont_emergencia, ant_personales, ant_alergicos) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (p.uid, p.nombre, p.rh, p.edad, p.religion, p.contEmergencia, p.antPersonales, p.antAlergicos))
        
        for c in p.consultas:
            cursor.execute("""
                INSERT INTO consulta_medica 
                (uid_paciente, codigo_registro_medico, motivo_consulta, diagnostico, fecha_consulta, temperatura, frecuencia_cardiaca, frecuencia_respiratoria) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (p.uid, c.medico.codigoRegistro, c.motivoConsulta, c.diagnostico, c.fechaConsulta, c.temp, c.fc, c.fr))
            
        db.commit()
        return {"mensaje": "Paciente y consulta registrados con éxito"}
    db.close()

@app.get("/pacientes/{uid}/consultas")
def obtener_consultas(uid: str):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT nombre FROM paciente WHERE UPPER(uid) = UPPER(%s);", (uid,))
        pac = cursor.fetchone()
        if not pac:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
            
        cursor.execute("""
            SELECT m.nombre, m.codigo_registro AS codigoRegistro, m.especialidad,
                   cm.motivo_consulta AS motivoConsulta, cm.diagnostico, 
                   cm.fecha_consulta AS fechaConsulta,
                   cm.temperatura AS temp, 
                   cm.frecuencia_cardiaca AS fc, 
                   cm.frecuencia_respiratoria AS fr
            FROM consulta_medica cm
            JOIN medico m ON cm.codigo_registro_medico = m.codigo_registro
            WHERE UPPER(cm.uid_paciente) = UPPER(%s);
        """, (uid,))
        consultas = cursor.fetchall()
        
        return {
            "paciente": pac["nombre"],
            "uid": uid,
            "totalConsultas": len(consultas),
            "consultas": consultas
        }
    db.close()

class LoginRequest(BaseModel):
    codigo: int
    contraseña: str

@app.post("/medicos/login")
def login_medico(credenciales: LoginRequest):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT nombre, codigo_registro AS codigoRegistro, especialidad, contraseña 
            FROM medico 
            WHERE codigo_registro = %s AND contraseña = %s;
        """, (credenciales.codigo, credenciales.contraseña))
        medico = cursor.fetchone()
        
        if not medico:
            raise HTTPException(status_code=404, detail="Credenciales incorrectas")
            
        return medico
    db.close()