import csv
import os
from datetime import datetime

pasta_script = os.path.dirname(os.path.abspath(__file__))
caminho_csv = os.path.join(pasta_script, "guias.csv")

CNPJ = "13348241000178"
REG_ANS = "344800"
CNES = "999999"
NOME_PRESTADOR = "PRESTADOR DE TESTE BLUE MED SAUDE"

# 🔥 GERA VALORES ÚNICOS (RESOLVE SEU ERRO)
agora = datetime.now()
numero_lote = agora.strftime('%Y%m%d%H%M%S')
sequencial = agora.strftime('%Y%m%d%H%M%S')

guias_xml = ""

with open(caminho_csv, newline='', encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)

    for linha in reader:
        valor_total = float(linha["valorUnitario"]) * int(linha["quantidade"])

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
</ans:guiaSP-SADT>
"""
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
    <ans:hash>TESTE123</ans:hash>
</ans:epilogo>
</ans:mensagemTISS>
"""

saida = os.path.join(pasta_script, "saida.xml")

with open(saida, "w", encoding="utf-8") as f:
    f.write(xml_final)

print("XML TISS GERADO COM LOTE ÚNICO!")
print("Lote:", numero_lote)