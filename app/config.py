
"""Configuração da aplicação, lida do ambiente.

Estratégia de banco de dados deste projeto:

| Ambiente | Banco | Como é fornecido |
|---|---|---|
| Desenvolvimento local | SQLite em arquivo | DATABASE_URL no arquivo .env |
| Produção | PostgreSQL | DATABASE_URL no ambiente de execução |
| Testes automatizados | SQLite em memória | DATABASE_URL definida pela suíte |

A variável DATABASE_URL é obrigatória e não possui valor padrão.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent

CAMINHO_DO_ENV = RAIZ_DO_PROJETO / ".env"


# ---------------------------------------------------------------------------
# Variáveis de ambiente
# ---------------------------------------------------------------------------

ENV_ENCONTRADO = load_dotenv(CAMINHO_DO_ENV)

ORIGENS_PADRAO = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

SEGREDO_DE_EXEMPLO = (
    "troque-este-segredo-de-desenvolvimento-por-um-gerado"
)

TAMANHO_MINIMO_DO_SEGREDO = 32

VALIDADE_PADRAO_EM_HORAS = 168.0


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def normalizar_url(url: str) -> str:
    """Normaliza URLs PostgreSQL para o driver psycopg."""

    url = url.strip()

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]

    return url


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Configuracao:
    """Parâmetros de execução da aplicação."""

    url_banco: str
    segredo_jwt: str
    origens_permitidas: tuple[str, ...] = ORIGENS_PADRAO
    echo_sql: bool = False
    validade_do_token_em_horas: float = VALIDADE_PADRAO_EM_HORAS

    @classmethod
    def do_ambiente(cls) -> Configuracao:
        """Monta a configuração a partir das variáveis de ambiente."""

        # DATABASE_URL é obrigatória
        database_url = os.getenv("DATABASE_URL", "").strip()

        if not database_url:
            raise RuntimeError(
                "A variável de ambiente DATABASE_URL não foi definida.\n"
                f"Esperado um arquivo .env em: {CAMINHO_DO_ENV}\n"
                "Configure DATABASE_URL no arquivo .env ou no ambiente."
            )

        # JWT_SECRET é obrigatório
        segredo_jwt = os.getenv("JWT_SECRET", "").strip()

        if not segredo_jwt:
            raise RuntimeError(
                "A variável de ambiente JWT_SECRET não foi definida.\n"
                f"Esperado um arquivo .env em: {CAMINHO_DO_ENV}\n"
                "Ela é a chave que assina os tokens de acesso.\n"
                "Gere um valor novo com:\n"
                '    python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        # Verifica o tamanho mínimo do segredo
        tamanho_segredo = len(segredo_jwt.encode("utf-8"))

        if tamanho_segredo < TAMANHO_MINIMO_DO_SEGREDO:
            raise RuntimeError(
                f"JWT_SECRET tem {tamanho_segredo} bytes e o "
                f"mínimo é {TAMANHO_MINIMO_DO_SEGREDO}.\n"
                "Gere um segredo adequado com:\n"
                '    python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        # Validade do token
        validade = os.getenv("JWT_EXPIRACAO_HORAS", "").strip()

        try:
            validade_em_horas = (
                float(validade)
                if validade
                else VALIDADE_PADRAO_EM_HORAS
            )
        except ValueError as erro:
            raise RuntimeError(
                "JWT_EXPIRACAO_HORAS precisa ser um número de horas; "
                f"recebido: {validade!r}."
            ) from erro

        if not 0 < validade_em_horas < float("inf"):
            raise RuntimeError(
                "JWT_EXPIRACAO_HORAS precisa ser um número finito "
                "maior que zero."
            )

        # Origens permitidas
        origens = os.getenv("ORIGENS_PERMITIDAS", "").strip()

        origens_permitidas = (
            tuple(
                origem.strip()
                for origem in origens.split(",")
                if origem.strip()
            )
            or ORIGENS_PADRAO
        )

        # Exibição das consultas SQL
        echo_sql = os.getenv("ECHO_SQL", "").strip().lower() in {
            "1",
            "true",
            "sim",
            "yes",
        }

        # Montagem da configuração
        configuracao = cls(
            url_banco=normalizar_url(database_url),
            segredo_jwt=segredo_jwt,
            origens_permitidas=origens_permitidas,
            echo_sql=echo_sql,
            validade_do_token_em_horas=validade_em_horas,
        )

        # Impede o uso do segredo de exemplo em banco de servidor
        if (
            configuracao.segredo_jwt == SEGREDO_DE_EXEMPLO
            and configuracao.banco_em_servidor
        ):
            raise RuntimeError(
                "JWT_SECRET ainda é o valor de exemplo do .env.example, "
                "e o banco configurado é um banco de servidor.\n"
                "Gere um segredo próprio com:\n"
                '    python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        return configuracao

    @property
    def dialeto(self) -> str:
        """Retorna o dialeto do banco utilizado."""

        return self.url_banco.split(":", 1)[0].split("+", 1)[0]

    @property
    def banco_em_memoria(self) -> bool:
        """Verifica se o SQLite está sendo executado em memória."""

        return self.dialeto == "sqlite" and (
            ":memory:" in self.url_banco
            or self.url_banco == "sqlite://"
        )

    @property
    def banco_em_servidor(self) -> bool:
        """Verifica se o banco está hospedado em servidor."""

        return self.dialeto != "sqlite"


# ---------------------------------------------------------------------------
# Instância global da configuração
# ---------------------------------------------------------------------------

@lru_cache
def obter_configuracao() -> Configuracao:
    """Retorna a configuração carregada uma única vez."""

    return Configuracao.do_ambiente()
