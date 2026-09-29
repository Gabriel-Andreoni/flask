from flask import Flask, render_template, request
import math

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("formulario.html")

@app.route("/result", methods=['POST'])
def result():
    salary_text = request.form.get("salary", "").strip()
    dependentsNumber_text = request.form.get("dependentsNumber", "").strip()
    
    if not salary_text:
        return "Informe o salário bruto", 400
    
    if not dependentsNumber_text:
        return "Informe o número de dependentes", 400
    
    try: 
        salary = float(salary_text)
    except ValueError:
        return "O salário deve ser um número válido", 400
    
    if not math.isfinite(salary):
        return "O salário deve ser um número finito", 400
    
    if salary < 0:
        return "O salário não pode ser negativo", 400
        
    try:
        dependentsNumber = int(dependentsNumber_text)
    except ValueError:
        return "O número de dependentes deve ser inteiro", 400
    
    if dependentsNumber < 0:
        return "O número de dependentes não pode ser negativo", 400
    
    if dependentsNumber > 10:
        return "Número de dependentes excede o limite permitido", 400
    
 
    liquidSalary = 0
    INSSDiscount = salary * 0.08
    taxes = (salary * 0.15)
    bonusPerChild = dependentsNumber * 200

    if(salary > 2500):
            liquidSalary = (salary - (INSSDiscount + taxes)) + bonusPerChild
    else:
        liquidSalary = (salary - INSSDiscount) + bonusPerChild
        taxes = 0

    return render_template('resultado.html', salary=salary, dependentsNumber=dependentsNumber, INSSDiscount=INSSDiscount, taxes=taxes, bonusPerChild=bonusPerChild, liquidSalary=liquidSalary)