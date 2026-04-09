from flask import Flask, render_template, request, jsonify, send_file, Response
import csv
import os
import json
import hashlib
import random
import io
from datetime import datetime

# PostgreSQL (opcional — usado quando DATABASE_URL está definido)
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_OK = True
except ImportError:
    PSYCOPG2_OK = False

app = Flask(__name__)
pasta_script = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get('DATABASE_URL')

# Railway envia postgres:// mas psycopg2 exige postgresql://
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

USA_POSTGRES = bool(DATABASE_URL and PSYCOPG2_OK)

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


# ── Banco de dados ────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Cria as tabelas se não existirem."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS contadores (
                    cnpj VARCHAR(14) PRIMARY KEY,
                    ultima_guia INTEGER DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sequenciais_usados (
                    cnpj VARCHAR(14) NOT NULL,
                    sequencial INTEGER NOT NULL,
                    PRIMARY KEY (cnpj, sequencial)
                )
            """)
        conn.commit()


# ── Contadores — PostgreSQL ───────────────────────────────────────────────────

def pg_contadores_cnpj(cnpj):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ultima_guia FROM contadores WHERE cnpj = %s", (cnpj,))
            row = cur.fetchone()
            ultima_guia = row[0] if row else 0
            cur.execute("SELECT COUNT(*) FROM sequenciais_usados WHERE cnpj = %s", (cnpj,))
            total_seq = cur.fetchone()[0]
    return {"sequenciais_usados": total_seq, "ultima_guia": ultima_guia}


def pg_gerar_sequencial_unico(cnpj):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT sequencial FROM sequenciais_usados WHERE cnpj = %s", (cnpj,))
            usados = {r[0] for r in cur.fetchall()}
            while True:
                novo = random.randint(100000, 999999)
                if novo not in usados:
                    break
            cur.execute(
                "INSERT INTO sequenciais_usados (cnpj, sequencial) VALUES (%s, %s)",
                (cnpj, novo)
            )
        conn.commit()
    return novo


def pg_incrementar_guia(cnpj):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO contadores (cnpj, ultima_guia) VALUES (%s, 1)
                ON CONFLICT (cnpj) DO UPDATE
                    SET ultima_guia = contadores.ultima_guia + 1
                RETURNING ultima_guia
            """, (cnpj,))
            numero = cur.fetchone()[0]
        conn.commit()
    return numero


# ── Contadores — Arquivo JSON (fallback local) ────────────────────────────────

def _ler_json():
    if os.path.exists(COUNTERS_FILE):
        with open(COUNTERS_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _salvar_json(c):
    with open(COUNTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(c, f, indent=2)


def json_contadores_cnpj(cnpj):
    c = _ler_json()
    dados = c.get(cnpj, {"sequenciais_usados": [], "ultima_guia": 0})
    return {
        "sequenciais_usados": len(dados.get("sequenciais_usados", [])),
        "ultima_guia": dados.get("ultima_guia", 0)
    }


def json_gerar_sequencial_unico(cnpj):
    c = _ler_json()
    if cnpj not in c:
        c[cnpj] = {"sequenciais_usados": [], "ultima_guia": 0}
    usados = set(c[cnpj].get("sequenciais_usados", []))
    while True:
        novo = random.randint(100000, 999999)
        if novo not in usados:
            usados.add(novo)
            break
    c[cnpj]["sequenciais_usados"] = list(usados)
    _salvar_json(c)
    return novo


def json_incrementar_guia(cnpj):
    c = _ler_json()
    if cnpj not in c:
        c[cnpj] = {"sequenciais_usados": [], "ultima_guia": 0}
    c[cnpj]["ultima_guia"] += 1
    _salvar_json(c)
    return c[cnpj]["ultima_guia"]


# ── Interface unificada ───────────────────────────────────────────────────────

def contadores_cnpj(cnpj):
    return pg_contadores_cnpj(cnpj) if USA_POSTGRES else json_contadores_cnpj(cnpj)

def gerar_sequencial_unico(cnpj):
    return pg_gerar_sequencial_unico(cnpj) if USA_POSTGRES else json_gerar_sequencial_unico(cnpj)

def incrementar_guia(cnpj):
    return pg_incrementar_guia(cnpj) if USA_POSTGRES else json_incrementar_guia(cnpj)

def gerar_numero_lote():
    return random.randint(100000, 999999)


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
    return jsonify(dados)


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
        sequencial = gerar_sequencial_unico(cnpj)
        numero_lote = gerar_numero_lote()

        for g in guias:
            g['numeroGuiaPrestador'] = g.get('numeroGuiaOperadora', '')

        xml_final = gerar_xml_tiss(config, guias, sequencial, numero_lote)

        # Salva localmente apenas se não for produção
        if not USA_POSTGRES:
            caminho_csv = os.path.join(pasta_script, "guias.csv")
            with open(caminho_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                writer.writerows(guias)

            saida = os.path.join(pasta_script, "saida.xml")
            with open(saida, 'w', encoding='utf-8') as f:
                f.write(xml_final)

        return jsonify({
            'success': True,
            'xml': xml_final,
            'sequencial': sequencial,
            'lote': numero_lote
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/download')
def download():
    xml = request.args.get('xml')
    if xml:
        # Em produção: retorna o XML recebido via query string não é viável
        # Usa sessão via POST body no frontend
        pass

    saida = os.path.join(pasta_script, "saida.xml")
    if os.path.exists(saida):
        return send_file(saida, as_attachment=True, download_name='saida.xml', mimetype='application/xml')
    return "Arquivo não encontrado.", 404


@app.route('/download', methods=['POST'])
def download_post():
    """Download do XML em produção (Railway não tem filesystem persistente)."""
    xml_content = request.json.get('xml', '')
    if not xml_content:
        return "XML não informado.", 400
    return Response(
        xml_content,
        mimetype='application/xml',
        headers={'Content-Disposition': 'attachment; filename=saida.xml'}
    )


# ── Inicialização ─────────────────────────────────────────────────────────────

if USA_POSTGRES:
    with app.app_context():
        init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    modo = "PostgreSQL" if USA_POSTGRES else "arquivo local (contadores.json)"
    print(f"Storage: {modo}")
    print(f"Acesse: http://localhost:{port}")
    app.run(debug=debug, host='0.0.0.0', port=port)
