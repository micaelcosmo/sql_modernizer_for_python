# ModernizeSQL: Pipeline Híbrido de Modernização (PL/pgSQL -> Python 3.14)

Este repositório contém o ModernizeSQL, uma solução de engenharia para a migração automatizada de lógica de negócio contida em Stored Procedures legadas ($PL/pgSQL$) para serviços modernos em Python 3.14. A solução utiliza uma abordagem híbrida, combinando parsing determinístico com Modelos de Linguagem de Grande Escala (LLM) orquestrados via LangGraph.

## 🎯 Objetivo

O objetivo principal é transformar procedimentos de banco de dados complexos em módulos Python legíveis, testáveis e escaláveis, mantendo a integridade semântica e tratando especificidades técnicas como cursores, transações e tipos complexos (JSONB).

## 🏗️ Arquitetura do Pipeline

A pipeline é modelada como um Grafo de Estados Acíclico Direcionado (DAG) utilizando o LangGraph. Cada nó do grafo possui uma responsabilidade única, garantindo a separação de interesses e facilitando a depuração.

### Fluxo de Execução (Diagrama de Grafo)

```mermaid
graph LR
    A((Início)) --> B[Parsing SQL]
    B --> C[Análise Semântica]
    C --> D[Geração LLM]
    D --> E[Validação Estática]
    E --> F{Sucesso?}
    F -- Sim --> G[Persistência DB]
    F -- Não --> H[Relatório de Erro]
    G --> I((Fim))
    H --> I
```

### Detalhamento dos Nós

- **Parsing Determinístico**: Utiliza a biblioteca pglast (baseada no parser oficial do PostgreSQL) para gerar uma árvore de sintaxe abstrata (AST) do código SQL original.
- **Análise Semântica**: Varre a AST em busca de padrões críticos: parâmetros IN/OUT, CTEs recursivas, bloqueios (FOR UPDATE), e manipulação de cursores. Atribui rótulos de risco que alimentam o prompt do LLM.
- **Geração Assistida (LLM)**: Através do OpenRouter, o sistema utiliza modelos de raciocínio (como DeepSeek ou Gemini) para traduzir a lógica. O prompt é enriquecido com o Anexo A (Schema do Banco) para garantir que as referências às tabelas e colunas sejam precisas.
- **Validação de Qualidade**: O código gerado é submetido ao ast.parse do Python. Se houver erro sintático (como indentação incorreta), o pipeline sinaliza falha no relatório.

## 🛠️ Decisões Técnicas e Trade-offs

- **Python 3.14 + SQLAlchemy 2.0**: Optamos por SQLAlchemy Core/ORM para gerenciar a camada de persistência no código moderno, garantindo tipagem forte e proteção contra SQL Injection.
- **Rewrite vs. Delegue**: A pipeline prioriza a reescrita da lógica em Python puro. Embora delegar o SQL bruto ao banco seja mais simples, a reescrita permite o uso de testes unitários granulares e reduz a dependência direta de funcionalidades proprietárias do SGBD.
- **OpenRouter**: Escolhido pela flexibilidade de trocar modelos (DeepSeek, Llama, Gemini) sem alterar a estrutura do código, permitindo otimização de custo e latência conforme a complexidade da procedure.
- **Persistência Assíncrona**: O uso de asyncpg e FastAPI garante que a API suporte alta concorrência sem travar o loop de eventos.

## 🚀 Como Executar

### 1. Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Configurações do Banco de Dados
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/modernizer_db

# Integração LLM via OpenRouter
OPENROUTER_API_KEY=sua_chave_aqui
```

### 2. Execução via Docker Compose (Recomendado)

Para subir o banco PostgreSQL e a API automaticamente:

```bash
docker-compose up -d
```

A API estará disponível em http://127.0.0.1:8000.

### 3. Execução Manual

Se preferir rodar localmente (necessário ter o PostgreSQL ativo):

```bash
# Instalar dependências
pip install -r requirements.txt

# Subir servidor
uvicorn main_api:app --reload
```

## 🧪 Estratégia de Testes (QA)

A suíte de testes (Pytest) valida a modernização de ponta a ponta utilizando os casos obrigatórios fornecidos:

- `test_fn_saldo_cliente`: Validação de funções de agregação simples (Anexo B).
- `test_sp_atualizar_status_contas_inativas`: Tratamento de parâmetros OUT e subqueries (Anexo C).
- `test_sp_transferir_entre_contas`: Gestão de transações atômicas e erros (Anexo D).
- `test_sp_processar_lote_taxas`: Lógica complexa com cursores e JSONB (Anexo E).
- `test_sp_relatorio_mensal_cliente`: O "chefe final" envolvendo CTEs recursivas e tabelas set-returning (Anexo F).

Para rodar os testes:

```bash
python -m pytest test/ -vv
```

## 📈 Escalabilidade e Evoluções Futuras

- **Suporte Multi-Dialeto**: Implementar novos nós de parsing para suportar T-SQL (SQL Server) e PL/SQL (Oracle).
- **Camada de Cache**: Cachear resultados de traduções para SQLs idênticos via Redis.
- **LLM-as-Judge**: Implementar um nó adicional que utiliza um modelo superior para validar se o Python gerado mantém a mesma lógica de negócio do SQL original (Equivalência Semântica).