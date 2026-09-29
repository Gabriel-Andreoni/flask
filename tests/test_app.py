"""Testes do comportamento HTTP e dos valores apresentados ao usuário."""

import unittest
from html.parser import HTMLParser

from app import app


class DemonstrativoParser(HTMLParser):
    """Lê os termos e valores do demonstrativo sem depender das classes CSS."""

    def __init__(self):
        super().__init__()
        self.valores = {}
        self.termo = None
        self.tag_atual = None
        self.partes = []

    def handle_starttag(self, tag, attrs):
        if tag in ("dt", "dd"):
            self.tag_atual = tag
            self.partes = []

    def handle_data(self, data):
        if self.tag_atual and data.strip():
            self.partes.append(data.strip())

    def handle_endtag(self, tag):
        if tag == self.tag_atual:
            if tag == "dt":
                # O primeiro texto é o rótulo; os demais são dicas de leitura.
                self.termo = self.partes[0] if self.partes else None
            elif self.termo:
                self.valores[self.termo] = " ".join(self.partes)
            self.tag_atual = None


class CalculadoraTestCase(unittest.TestCase):
    def setUp(self):
        testing_anterior = app.config["TESTING"]
        app.config["TESTING"] = True
        self.addCleanup(app.config.update, TESTING=testing_anterior)
        self.client = app.test_client()

    def test_pagina_inicial_apresenta_formulario(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/html")
        html = response.get_data(as_text=True)
        self.assertIn('name="salary"', html)
        self.assertIn('name="dependentsNumber"', html)
        self.assertIn('action="/result"', html)
        self.assertIn('method="post"', html)

    def test_calculos_e_formatacao_do_demonstrativo(self):
        # Resultados explícitos: o teste não repete a fórmula da implementação.
        casos = [
            ("0", "0", ("0,00", "0,00", "0,00", "0,00", "0,00")),
            ("2000", "0", ("2.000,00", "160,00", "0,00", "0,00", "1.840,00")),
            ("2500", "1", ("2.500,00", "200,00", "0,00", "200,00", "2.500,00")),
            ("2500.01", "0", ("2.500,01", "200,00", "375,00", "0,00", "1.925,01")),
            ("3000", "2", ("3.000,00", "240,00", "450,00", "400,00", "2.710,00")),
            ("3000", "10", ("3.000,00", "240,00", "450,00", "2.000,00", "4.310,00")),
            (" 3000 ", " 2 ", ("3.000,00", "240,00", "450,00", "400,00", "2.710,00")),
            ("1234.56", "2", ("1.234,56", "98,76", "0,00", "400,00", "1.535,80")),
        ]
        for salario, dependentes, valores in casos:
            with self.subTest(salario=salario, dependentes=dependentes):
                response = self.client.post("/result", data={
                    "salary": salario, "dependentsNumber": dependentes,
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "text/html")
                parser = DemonstrativoParser()
                parser.feed(response.get_data(as_text=True))
                bruto, inss, imposto, bonus, liquido = valores
                self.assertEqual(parser.valores, {
                    "Salário bruto": f"R$ {bruto}",
                    "Contribuição INSS": f"− R$ {inss}",
                    "Imposto de renda": f"− R$ {imposto}",
                    "Bônus por dependentes": f"+ R$ {bonus}",
                    "Salário líquido": f"R$ {liquido}",
                })

    def test_entradas_nao_numericas_apresentam_mensagem(self):
        casos = [
            ("abc", "0", "O salário deve ser um número válido"),
            ("2000", "abc", "O número de dependentes deve ser inteiro"),
            ("2000", "1.5", "O número de dependentes deve ser inteiro"),
        ]
        for salario, dependentes, mensagem in casos:
            with self.subTest(salario=salario, dependentes=dependentes):
                response = self.client.post("/result", data={
                    "salary": salario, "dependentsNumber": dependentes,
                })
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_data(as_text=True), mensagem)

    def test_campos_ausentes_retornam_bad_request(self):
        casos = [
            ({"salary": "2000"}, "Informe o número de dependentes"),
            ({"dependentsNumber": "0"}, "Informe o salário bruto"),
            ({}, "Informe o salário bruto"),
        ]
        for dados, mensagem in casos:
            with self.subTest(dados=dados):
                response = self.client.post("/result", data=dados)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_data(as_text=True), mensagem)

    def test_campos_vazios_ou_em_branco_retornam_mensagem(self):
        for campo, mensagem in [
            ("salary", "Informe o salário bruto"),
            ("dependentsNumber", "Informe o número de dependentes"),
        ]:
            for valor in ["", "   ", "\t\n"]:
                with self.subTest(campo=campo, valor=valor):
                    dados = {"salary": "3000", "dependentsNumber": "2"}
                    dados[campo] = valor
                    response = self.client.post("/result", data=dados)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_data(as_text=True), mensagem)

    def test_valores_negativos_sao_rejeitados(self):
        for campo, mensagem in [
            ("salary", "O salário não pode ser negativo"),
            ("dependentsNumber", "O número de dependentes não pode ser negativo"),
        ]:
            with self.subTest(campo=campo):
                dados = {"salary": "3000", "dependentsNumber": "2"}
                dados[campo] = "-1"
                response = self.client.post("/result", data=dados)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_data(as_text=True), mensagem)

    def test_salario_nao_finito_e_rejeitado(self):
        for salario in ["nan", "inf", "-inf", "1e999"]:
            with self.subTest(salario=salario):
                response = self.client.post("/result", data={
                    "salary": salario, "dependentsNumber": "0",
                })
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_data(as_text=True),
                    "O salário deve ser um número finito",
                )

    def test_dependentes_acima_do_limite_sao_rejeitados(self):
        # O número com 309 dígitos provocava OverflowError durante o cálculo.
        for dependentes in ["11", "9" * 309]:
            with self.subTest(dependentes=dependentes):
                response = self.client.post("/result", data={
                    "salary": "3000", "dependentsNumber": dependentes,
                })
                self.assertEqual(response.status_code, 400)
                self.assertIn("limite permitido", response.get_data(as_text=True))

    def test_resultado_nao_aceita_get(self):
        self.assertEqual(self.client.get("/result").status_code, 405)

    def test_css_e_fontes_estao_disponiveis(self):
        caminhos = [
            "/static/formulario.css",
            "/static/resultado.css",
            "/static/fonts/dm-sans-regular.ttf",
            "/static/fonts/dm-sans-bold.ttf",
            "/static/fonts/libre-caslon-display.ttf",
        ]
        for caminho in caminhos:
            with self.subTest(caminho=caminho):
                response = self.client.get(caminho)
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data)
                if caminho.endswith(".css"):
                    self.assertEqual(response.mimetype, "text/css")


if __name__ == "__main__":
    unittest.main()
