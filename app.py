from flask import Flask, render_template, request, jsonify, send_file
import csv
import os
import json
import hashlib
import random
from datetime import datetime
import io

app = Flask(__name__)
pasta_script = os.path.dirname(os.path.abspath(__file__))

CSV_FIELDS = [
    'numeroGuiaPrestador', 'numeroGuiaOperadora', 'senha',
    'dataAutorizacao', 'dataValidadeSenha', 'numeroCarteira',
    'nomeBeneficiario', 'nomeProfissional', 'conselho',
    'numeroConselho', 'uf', 'cbos', 'dataSolicitacao',
    'dataExecucao', 'horaInicial', 'horaFinal',
    'codigoProcedimento', 'descricaoProcedimento',
    'quantidade', 'valorUnitario', 'cpfProfissional', 'nomeProfExec'
]

CONFIG_PADRAO = {
    'cnpj': '13348241000178',
    'reg_ans': '344800',
    'cnes': '999999',
    'nome_prestador': 'PRESTADOR DE TESTE BLUE MED SAUDE'
}

COUNTERS_FILE = os.path.join(pasta_script, "contadores.json")


# ── Contadores ────────────────────────────────────────────────────────────────

def ler_contadores():
    if os.path.exists(COUNTERS_FILE):
        with open(COUNTERS_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def salvar_contadores(c):
    with open(COUNTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(c, f, indent=2)


def contadores_cnpj(cnpj):
    """Retorna os contadores do CNPJ (sem modificar)."""
    c = ler_contadores()
    return c.get(cnpj, {"sequenciais_usados": [], "ultima_guia": 0})


def gerar_sequencial_unico(cnpj):
    """Gera um sequencial aleatório de 6 dígitos único para o CNPJ."""
    c = ler_contadores()
    if cnpj not in c:
        c[cnpj] = {"sequenciais_usados": [], "ultima_guia": 0}

    usados = set(c[cnpj].get("sequenciais_usados", []))
    while True:
        novo = random.randint(100000, 999999)
        if novo not in usados:
            usados.add(novo)
            break

    c[cnpj]["sequenciais_usados"] = list(usados)
    salvar_contadores(c)
    return novo


def gerar_numero_lote():
    """Gera um número de lote aleatório de 6 dígitos."""
    return random.randint(100000, 999999)


def incrementar_guia(cnpj):
    """Incrementa e retorna o próximo número de guia para o CNPJ."""
    c = ler_contadores()
    if cnpj not in c:
        c[cnpj] = {"sequenciais_usados": [], "ultima_guia": 0}
    c[cnpj]["ultima_guia"] += 1
    salvar_contadores(c)
    return c[cnpj]["ultima_guia"]


def atualizar_ultima_guia(cnpj, valor):
    """Garante que ultima_guia seja ao menos `valor`."""
    c = ler_contadores()
    if cnpj not in c:
        c[cnpj] = {"sequenciais_usados": [], "ultima_guia": 0}
    if valor > c[cnpj].get("ultima_guia", 0):
        c[cnpj]["ultima_guia"] = valor
        salvar_contadores(c)


# ── CSV ───────────────────────────────────────────────────────────────────────

def ler_guias():
    guias = []
    caminho_csv = os.path.join(pasta_script, "guias.csv")
    if os.path.exists(caminho_csv):
        with open(caminho_csv, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                guias.append(dict(row))
    return guias


# ── Geração do XML ────────────────────────────────────────────────────────────

def gerar_xml_tiss(config, guias, sequencial, numero_lote):
    CNPJ = config['cnpj']
    REG_ANS = config['reg_ans']
    CNES = config['cnes']
    NOME_PRESTADOR = config['nome_prestador']

    agora = datetime.now()
    guias_xml = ""

    for linha in guias:
        valor_total = float(linha['valorUnitario']) * int(linha['quantidade'])
        guia = f"""
<ans:guiaSP-SADT>
    <ans:cabecalhoGuia>
        <ans:registroANS>{REG_ANS}</ans:registroANS>
        <ans:numeroGuiaPrestador>{linha['numeroGuiaPrestador']}</ans:numeroGuiaPrestador>
        <ans:guiaPrincipal>{linha['numeroGuiaPrestador']}</ans:guiaPrincipal>
    </ans:cabecalhoGuia>

    <ans:dadosAutorizacao>
        <ans:numeroGuiaOperadora>{linha['numeroGuiaOperadora']}</ans:numeroGuiaOperadora>
        <ans:dataAutorizacao>{linha['dataAutorizacao']}</ans:dataAutorizacao>
        <ans:senha>{linha['senha']}</ans:senha>
        <ans:dataValidadeSenha>{linha['dataValidadeSenha']}</ans:dataValidadeSenha>
    </ans:dadosAutorizacao>

    <ans:dadosBeneficiario>
        <ans:numeroCarteira>{linha['numeroCarteira']}</ans:numeroCarteira>
        <ans:atendimentoRN>N</ans:atendimentoRN>
        <ans:nomeBeneficiario>{linha['nomeBeneficiario']}</ans:nomeBeneficiario>
    </ans:dadosBeneficiario>

    <ans:dadosSolicitante>
        <ans:contratadoSolicitante>
            <ans:cnpjContratado>{CNPJ}</ans:cnpjContratado>
            <ans:nomeContratado>{NOME_PRESTADOR}</ans:nomeContratado>
        </ans:contratadoSolicitante>
        <ans:profissionalSolicitante>
            <ans:nomeProfissional>{linha['nomeProfissional']}</ans:nomeProfissional>
            <ans:conselhoProfissional>{linha['conselho']}</ans:conselhoProfissional>
            <ans:numeroConselhoProfissional>{linha['numeroConselho']}</ans:numeroConselhoProfissional>
            <ans:UF>{linha['uf']}</ans:UF>
            <ans:CBOS>{linha['cbos']}</ans:CBOS>
        </ans:profissionalSolicitante>
    </ans:dadosSolicitante>

    <ans:dadosSolicitacao>
        <ans:dataSolicitacao>{linha['dataSolicitacao']}</ans:dataSolicitacao>
        <ans:caraterAtendimento>1</ans:caraterAtendimento>
        <ans:indicacaoClinica>TESTE</ans:indicacaoClinica>
    </ans:dadosSolicitacao>

    <ans:dadosExecutante>
        <ans:contratadoExecutante>
            <ans:cnpjContratado>{CNPJ}</ans:cnpjContratado>
            <ans:nomeContratado>{NOME_PRESTADOR}</ans:nomeContratado>
        </ans:contratadoExecutante>
        <ans:CNES>{CNES}</ans:CNES>
    </ans:dadosExecutante>

    <ans:dadosAtendimento>
        <ans:tipoAtendimento>05</ans:tipoAtendimento>
        <ans:indicacaoAcidente>9</ans:indicacaoAcidente>
        <ans:tipoConsulta>1</ans:tipoConsulta>
    </ans:dadosAtendimento>

    <ans:procedimentosExecutados>
        <ans:procedimentoExecutado>
            <ans:dataExecucao>{linha['dataExecucao']}</ans:dataExecucao>
            <ans:horaInicial>{linha['horaInicial']}</ans:horaInicial>
            <ans:horaFinal>{linha['horaFinal']}</ans:horaFinal>
            <ans:procedimento>
                <ans:codigoTabela>22</ans:codigoTabela>
                <ans:codigoProcedimento>{linha['codigoProcedimento']}</ans:codigoProcedimento>
                <ans:descricaoProcedimento>{linha['descricaoProcedimento']}</ans:descricaoProcedimento>
            </ans:procedimento>
            <ans:quantidadeExecutada>{linha['quantidade']}</ans:quantidadeExecutada>
            <ans:viaAcesso>1</ans:viaAcesso>
            <ans:tecnicaUtilizada>1</ans:tecnicaUtilizada>
            <ans:reducaoAcrescimo>1.00</ans:reducaoAcrescimo>
            <ans:valorUnitario>{linha['valorUnitario']}</ans:valorUnitario>
            <ans:valorTotal>{valor_total:.2f}</ans:valorTotal>
            <ans:equipeSadt>
                <ans:grauPart>00</ans:grauPart>
                <ans:codProfissional>
                    <ans:cpfContratado>{linha['cpfProfissional']}</ans:cpfContratado>
                </ans:codProfissional>
                <ans:nomeProf>{linha['nomeProfExec']}</ans:nomeProf>
                <ans:conselho>{linha['conselho']}</ans:conselho>
                <ans:numeroConselhoProfissional>{linha['numeroConselho']}</ans:numeroConselhoProfissional>
                <ans:UF>{linha['uf']}</ans:UF>
                <ans:CBOS>{linha['cbos']}</ans:CBOS>
            </ans:equipeSadt>
        </ans:procedimentoExecutado>
    </ans:procedimentosExecutados>

    <ans:valorTotal>
        <ans:valorProcedimentos>{valor_total:.2f}</ans:valorProcedimentos>
        <ans:valorTotalGeral>{valor_total:.2f}</ans:valorTotalGeral>
    </ans:valorTotal>
</ans:guiaSP-SADT>"""
        guias_xml += guia

    xml_final = f"""<?xml version="1.0" encoding="UTF-8"?>
<ans:mensagemTISS xmlns:ans="http://www.ans.gov.br/padroes/tiss/schemas">
<ans:cabecalho>
    <ans:identificacaoTransacao>
        <ans:tipoTransacao>ENVIO_LOTE_GUIAS</ans:tipoTransacao>
        <ans:sequencialTransacao>{sequencial}</ans:sequencialTransacao>
        <ans:dataRegistroTransacao>{agora.strftime('%Y-%m-%d')}</ans:dataRegistroTransacao>
        <ans:horaRegistroTransacao>{agora.strftime('%H:%M:%S')}</ans:horaRegistroTransacao>
    </ans:identificacaoTransacao>
    <ans:origem>
        <ans:identificacaoPrestador>
            <ans:CNPJ>{CNPJ}</ans:CNPJ>
        </ans:identificacaoPrestador>
    </ans:origem>
    <ans:destino>
        <ans:registroANS>{REG_ANS}</ans:registroANS>
    </ans:destino>
    <ans:Padrao>3.03.01</ans:Padrao>
</ans:cabecalho>

<ans:prestadorParaOperadora>
    <ans:loteGuias>
        <ans:numeroLote>{numero_lote}</ans:numeroLote>
        <ans:guiasTISS>
            {guias_xml}
        </ans:guiasTISS>
    </ans:loteGuias>
</ans:prestadorParaOperadora>

<ans:epilogo>
    <ans:hash></ans:hash>
</ans:epilogo>
</ans:mensagemTISS>"""

    hash_md5 = hashlib.md5(xml_final.encode('utf-8')).hexdigest()
    xml_final = xml_final.replace('<ans:hash></ans:hash>', f'<ans:hash>{hash_md5}</ans:hash>')

    return xml_final


# ── Rotas ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    guias = ler_guias()
    return render_template('index.html', guias=guias, config=CONFIG_PADRAO)


@app.route('/api/contadores')
def api_contadores():
    cnpj = request.args.get('cnpj', '').strip()
    dados = contadores_cnpj(cnpj)
    return jsonify({
        "sequenciais_usados": len(dados.get("sequenciais_usados", [])),
        "ultima_guia": dados.get("ultima_guia", 0)
    })


@app.route('/api/proximo_guia')
def api_proximo_guia():
    cnpj = request.args.get('cnpj', '').strip()
    numero = incrementar_guia(cnpj)
    return jsonify({"numero": numero, "formatado": str(numero).zfill(4)})


@app.route('/gerar', methods=['POST'])
def gerar():
    data = request.json
    config = data.get('config', CONFIG_PADRAO)
    guias = data.get('guias', [])

    if not guias:
        return jsonify({'success': False, 'error': 'Nenhuma guia adicionada.'})

    config = {k: v.strip() for k, v in config.items()}
    guias = [{k: v.strip() if isinstance(v, str) else v for k, v in g.items()} for g in guias]

    try:
        cnpj = config['cnpj']

        # sequencialTransacao: aleatório 6 dígitos, único por CNPJ
        sequencial = gerar_sequencial_unico(cnpj)

        # numeroLote: aleatório 6 dígitos (independente)
        numero_lote = gerar_numero_lote()

        # numeroGuiaPrestador espelha numeroGuiaOperadora
        for g in guias:
            g['numeroGuiaPrestador'] = g.get('numeroGuiaOperadora', '')

        xml_final = gerar_xml_tiss(config, guias, sequencial, numero_lote)

        caminho_csv = os.path.join(pasta_script, "guias.csv")
        with open(caminho_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(guias)

        saida = os.path.join(pasta_script, "saida.xml")
        with open(saida, 'w', encoding='utf-8') as f:
            f.write(xml_final)

        return jsonify({'success': True, 'xml': xml_final, 'sequencial': sequencial, 'lote': numero_lote})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/download')
def download():
    saida = os.path.join(pasta_script, "saida.xml")
    if os.path.exists(saida):
        return send_file(saida, as_attachment=True, download_name='saida.xml', mimetype='application/xml')
    return "Arquivo não encontrado.", 404


if __name__ == '__main__':
    print("Acesse: http://localhost:5000")
    app.run(debug=True, port=5000)
