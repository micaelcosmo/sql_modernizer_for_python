import httpx
import pytest

# URL padrao do Uvicorn para execucao em terminais separados
BASE_URL = "http://127.0.0.1:8000"

# Anexo A - Schema do banco legado (Fornecido como contexto para enriquecer o prompt)
SCHEMA_CONTEXT = """
CREATE TABLE clientes (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    cpf CHAR(11) NOT NULL UNIQUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'ATIVO' CHECK (status IN ('ATIVO','INATIVO','BLOQUEADO'))
);

CREATE TABLE contas (
    id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL REFERENCES clientes(id),
    agencia VARCHAR(10) NOT NULL,
    numero VARCHAR(20) NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('CORRENTE','POUPANCA','SALARIO')),
    saldo NUMERIC(18,2) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'ATIVA' CHECK (status IN ('ATIVA','INATIVA','ENCERRADA')),
    data_abertura TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (agencia, numero)
);

CREATE TABLE transacoes (
    id BIGSERIAL PRIMARY KEY,
    conta_origem_id BIGINT REFERENCES contas(id),
    conta_destino_id BIGINT REFERENCES contas(id),
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('DEPOSITO','SAQUE','TRANSFERENCIA','TARIFA')),
    valor NUMERIC(18,2) NOT NULL CHECK (valor > 0),
    data_transacao TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'EFETIVADA' CHECK (status IN ('EFETIVADA','CANCELADA','ESTORNADA'))
);

CREATE TABLE taxas (
    id BIGSERIAL PRIMARY KEY,
    tipo_operacao VARCHAR(20) NOT NULL,
    percentual NUMERIC(7,4) NOT NULL DEFAULT 0,
    valor_minimo NUMERIC(18,2) NOT NULL DEFAULT 0,
    vigente_de DATE NOT NULL,
    vigente_ate DATE
);

CREATE TABLE log_auditoria (
    id BIGSERIAL PRIMARY KEY,
    entidade VARCHAR(50) NOT NULL,
    entidade_id BIGINT,
    acao VARCHAR(50) NOT NULL,
    detalhes JSONB,
    criado_em TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


def test_fn_saldo_cliente():
    """
    Testa a modernizacao da funcao escalar fn_saldo_cliente (Anexo B).
    Complexidade: Baixa.
    """
    sql_code = """
    CREATE OR REPLACE FUNCTION fn_saldo_cliente(p_cliente_id BIGINT)
    RETURNS NUMERIC(18,2)
    LANGUAGE plpgsql
    AS $$
    DECLARE
     v_total NUMERIC(18,2);
    BEGIN
     SELECT COALESCE(SUM(saldo), 0)
     INTO v_total
     FROM contas
     WHERE cliente_id = p_cliente_id
     AND status = 'ATIVA';
     RETURN v_total;
    END;
    $$;
    """
    
    payload = {"sql_code": sql_code, "schema_context": SCHEMA_CONTEXT}
    response = httpx.post(f"{BASE_URL}/modernize", json=payload, timeout=90.0)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == "sucesso", f"Erro: {data.get('report')}"
    assert "generated_code" in data


def test_sp_atualizar_status_contas_inativas():
    """
    Testa a modernizacao da procedure sp_atualizar_status_contas_inativas (Anexo C).
    Complexidade: Baixa-Media.
    """
    sql_code = """
    CREATE OR REPLACE PROCEDURE sp_atualizar_status_contas_inativas(
     IN p_dias INT,
     OUT p_afetadas INT
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
     IF p_dias IS NULL OR p_dias <= 0 THEN
     RAISE EXCEPTION 'Parametro p_dias deve ser positivo, recebido: %', p_dias;
     END IF;
     UPDATE contas c
     SET status = 'INATIVA'
     WHERE c.status = 'ATIVA'
     AND NOT EXISTS (
     SELECT 1
     FROM transacoes t
     WHERE (t.conta_origem_id = c.id OR t.conta_destino_id = c.id)
     AND t.data_transacao >= NOW() - (p_dias || ' days')::INTERVAL
     );
     GET DIAGNOSTICS p_afetadas = ROW_COUNT;
     INSERT INTO log_auditoria (entidade, acao, detalhes)
     VALUES (
     'contas',
     'INATIVACAO_LOTE',
     jsonb_build_object('dias', p_dias, 'afetadas', p_afetadas)
     );
    END;
    $$;
    """
    
    payload = {"sql_code": sql_code, "schema_context": SCHEMA_CONTEXT}
    response = httpx.post(f"{BASE_URL}/modernize", json=payload, timeout=90.0)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == "sucesso", f"Erro: {data.get('report')}"
    assert "generated_code" in data


def test_sp_transferir_entre_contas():
    """
    Testa a modernizacao da procedure sp_transferir_entre_contas (Anexo D).
    Complexidade: Media.
    """
    sql_code = """
    CREATE OR REPLACE PROCEDURE sp_transferir_entre_contas(
     IN p_conta_origem BIGINT,
     IN p_conta_destino BIGINT,
     IN p_valor NUMERIC(18,2)
    )
    LANGUAGE plpgsql
    AS $$
    DECLARE
     v_saldo_origem NUMERIC(18,2);
     v_status_origem VARCHAR(20);
     v_status_destino VARCHAR(20);
    BEGIN
     IF p_valor IS NULL OR p_valor <= 0 THEN
     RAISE EXCEPTION 'Valor invalido para transferencia: %', p_valor;
     END IF;
     IF p_conta_origem = p_conta_destino THEN
     RAISE EXCEPTION 'Conta de origem e destino nao podem ser iguais';
     END IF;
     SELECT saldo, status INTO v_saldo_origem, v_status_origem
     FROM contas WHERE id = p_conta_origem FOR UPDATE;
     SELECT status INTO v_status_destino
     FROM contas WHERE id = p_conta_destino FOR UPDATE;
     IF v_saldo_origem IS NULL THEN
     RAISE EXCEPTION 'Conta de origem % nao encontrada', p_conta_origem;
     END IF;
     IF v_status_origem <> 'ATIVA' OR v_status_destino <> 'ATIVA' THEN
     RAISE EXCEPTION 'Ambas as contas precisam estar ATIVAS';
     END IF;
     IF v_saldo_origem < p_valor THEN
     RAISE EXCEPTION 'Saldo insuficiente: saldo=% valor=%', v_saldo_origem, p_valor;
     END IF;
     UPDATE contas SET saldo = saldo - p_valor WHERE id = p_conta_origem;
     UPDATE contas SET saldo = saldo + p_valor WHERE id = p_conta_destino;
     INSERT INTO transacoes (conta_origem_id, conta_destino_id, tipo, valor)
     VALUES (p_conta_origem, p_conta_destino, 'TRANSFERENCIA', p_valor);
     INSERT INTO log_auditoria (entidade, entidade_id, acao, detalhes)
     VALUES (
     'transacoes',
     NULL,
     'TRANSFERENCIA_OK',
     jsonb_build_object(
     'origem', p_conta_origem,
     'destino', p_conta_destino,
     'valor', p_valor
     )
     );
    EXCEPTION
     WHEN OTHERS THEN
     INSERT INTO log_auditoria (entidade, acao, detalhes)
     VALUES (
     'transacoes',
     'TRANSFERENCIA_ERRO',
     jsonb_build_object(
     'origem', p_conta_origem,
     'destino', p_conta_destino,
     'valor', p_valor,
     'erro', SQLERRM
     )
     );
     RAISE;
    END;
    $$;
    """
    
    payload = {"sql_code": sql_code, "schema_context": SCHEMA_CONTEXT}
    response = httpx.post(f"{BASE_URL}/modernize", json=payload, timeout=90.0)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == "sucesso", f"Erro: {data.get('report')}"
    assert "generated_code" in data


def test_sp_processar_lote_taxas():
    """
    Testa a modernizacao da procedure sp_processar_lote_taxas (Anexo E).
    Complexidade: Alta.
    """
    sql_code = """
    CREATE OR REPLACE PROCEDURE sp_processar_lote_taxas(
     IN p_data_referencia DATE
    )
    LANGUAGE plpgsql
    AS $$
    DECLARE
     cur_transacoes CURSOR FOR
     SELECT id, conta_origem_id, tipo, valor
     FROM transacoes
     WHERE DATE(data_transacao) = p_data_referencia
     AND status = 'EFETIVADA'
     AND tipo <> 'TARIFA';
     v_id BIGINT;
     v_origem BIGINT;
     v_tipo VARCHAR(20);
     v_valor NUMERIC(18,2);
     v_taxa NUMERIC(18,2);
     v_percentual NUMERIC(7,4);
     v_minimo NUMERIC(18,2);
     v_total_taxas NUMERIC(18,2) := 0;
     v_count INT := 0;
    BEGIN
     OPEN cur_transacoes;
     LOOP
     FETCH cur_transacoes INTO v_id, v_origem, v_tipo, v_valor;
     EXIT WHEN NOT FOUND;
     SELECT percentual, valor_minimo
     INTO v_percentual, v_minimo
     FROM taxas
     WHERE tipo_operacao = v_tipo
     AND vigente_de <= p_data_referencia
     AND (vigente_ate IS NULL OR vigente_ate >= p_data_referencia)
     ORDER BY vigente_de DESC
     LIMIT 1;
     IF v_percentual IS NULL THEN
     CONTINUE;
     END IF;
     v_taxa := GREATEST(v_valor * v_percentual / 100.0, v_minimo);
     CASE v_tipo
     WHEN 'TRANSFERENCIA' THEN v_taxa := v_taxa;
     WHEN 'SAQUE' THEN v_taxa := v_taxa * 1.10;
     ELSE v_taxa := v_taxa * 0.90;
     END CASE;
     IF v_origem IS NOT NULL THEN
     UPDATE contas SET saldo = saldo - v_taxa WHERE id = v_origem;
     INSERT INTO transacoes (conta_origem_id, tipo, valor, status)
     VALUES (v_origem, 'TARIFA', v_taxa, 'EFETIVADA');
     INSERT INTO log_auditoria (entidade, entidade_id, acao, detalhes)
     VALUES (
     'transacoes', v_id, 'TARIFA_APLICADA',
     jsonb_build_object(
     'transacao_origem', v_id,
    'tipo_origem', v_tipo,
    'valor_origem', v_valor,
    'percentual', v_percentual,
    'taxa_aplicada', v_taxa
     )
     );
     v_total_taxas := v_total_taxas + v_taxa;
     v_count := v_count + 1;
     END IF;
     END LOOP;
     CLOSE cur_transacoes;
     INSERT INTO log_auditoria (entidade, acao, detalhes)
     VALUES (
     'lote_taxas', 'LOTE_PROCESSADO',
     jsonb_build_object(
     'data_referencia', p_data_referencia,
     'transacoes', v_count,
     'total_taxas', v_total_taxas
     )
     );
    END;
    $$;
    """
    
    payload = {"sql_code": sql_code, "schema_context": SCHEMA_CONTEXT}
    response = httpx.post(f"{BASE_URL}/modernize", json=payload, timeout=90.0)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == "sucesso", f"Erro: {data.get('report')}"
    assert "generated_code" in data


def test_sp_relatorio_mensal_cliente():
    """
    Testa a modernizacao da funcao sp_relatorio_mensal_cliente (Anexo F).
    Complexidade: Muito Alta.
    """
    sql_code = """
    CREATE OR REPLACE FUNCTION sp_relatorio_mensal_cliente(
     p_cliente_id BIGINT,
     p_data_inicio DATE,
     p_data_fim DATE
    )
    RETURNS TABLE (
     mes_referencia DATE,
     total_creditos NUMERIC(18,2),
     total_debitos NUMERIC(18,2),
     saldo_consolidado NUMERIC(18,2),
     qtd_transacoes INT
    )
    LANGUAGE plpgsql
    AS $$
    DECLARE
     v_saldo_atual NUMERIC(18,2);
    BEGIN
     IF p_data_inicio > p_data_fim THEN
     RAISE EXCEPTION 'Periodo invalido: inicio % > fim %', p_data_inicio, p_data_fim;
     END IF;
     v_saldo_atual := fn_saldo_cliente(p_cliente_id);
     RAISE NOTICE 'Saldo atual do cliente %: %', p_cliente_id, v_saldo_atual;
     RETURN QUERY
     WITH RECURSIVE meses AS (
     SELECT DATE_TRUNC('month', p_data_inicio)::DATE AS mes
     UNION ALL
     SELECT (mes + INTERVAL '1 month')::DATE
     FROM meses
     WHERE mes < DATE_TRUNC('month', p_data_fim)
     ),
     movimento AS (
     SELECT
     DATE_TRUNC('month', t.data_transacao)::DATE AS mes,
     SUM(CASE WHEN t.conta_destino_id IN (
     SELECT id FROM contas WHERE cliente_id = p_cliente_id
     ) THEN t.valor ELSE 0 END) AS creditos,
     SUM(CASE WHEN t.conta_origem_id IN (
     SELECT id FROM contas WHERE cliente_id = p_cliente_id
     ) THEN t.valor ELSE 0 END) AS debitos,
     COUNT(*) AS qtd
     FROM transacoes t
     WHERE t.status = 'EFETIVADA'
     AND t.data_transacao >= p_data_inicio
     AND t.data_transacao < p_data_fim + INTERVAL '1 day'
     AND (
     t.conta_origem_id IN (SELECT id FROM contas WHERE cliente_id = p_cliente_id)
     OR t.conta_destino_id IN (SELECT id FROM contas WHERE cliente_id = p_cliente_id)
     )
     GROUP BY 1
     )
     SELECT
     m.mes AS mes_referencia,
     COALESCE(mv.creditos, 0) AS total_creditos,
     COALESCE(mv.debitos, 0) AS total_debitos,
     v_saldo_atual + COALESCE(mv.creditos, 0)
     - COALESCE(mv.debitos, 0) AS saldo_consolidado,
     COALESCE(mv.qtd, 0)::INT AS qtd_transacoes
     FROM meses m
     LEFT JOIN movimento mv ON mv.mes = m.mes
     ORDER BY m.mes;
    EXCEPTION
     WHEN OTHERS THEN
     RAISE WARNING 'Falha ao gerar relatorio: %. Retornando linha de fallback.',
    SQLERRM;
     RETURN QUERY
     SELECT
     DATE_TRUNC('month', p_data_inicio)::DATE,
     0::NUMERIC(18,2),
     0::NUMERIC(18,2),
     COALESCE(v_saldo_atual, 0),
     0::INT;
    END;
    $$;
    """
    
    payload = {"sql_code": sql_code, "schema_context": SCHEMA_CONTEXT}
    response = httpx.post(f"{BASE_URL}/modernize", json=payload, timeout=120.0)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == "sucesso", f"Erro: {data.get('report')}"
    assert "generated_code" in data