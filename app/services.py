
"""
Serviços de aplicação: onde as operações do sistema são orquestradas.

Um serviço recebe repositórios e colaboradores pelo construtor (injeção de
dependência), aplica as regras de negócio e levanta exceções de domínio. Ele
não conhece HTTP: não importa `fastapi`, não devolve códigos de status. O
mesmo serviço funcionaria em um programa de terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.enums import PrioridadeTarefa, StatusTarefa
from app.exceptions import (
    AcessoNaoAutorizado,
    CredenciaisInvalidas,
    EmailJaCadastrado,
    TarefaNaoEncontrada,
    UsuarioNaoEncontrado,
)
from app.models import Tarefa, Usuario
from app.repositories import FiltroDeTarefas, TarefaRepositorio, UsuarioRepositorio
from app.security import HashDeSenha


# Sentinela para distinguir "campo não enviado" de "campo enviado como null".
NAO_INFORMADO: Any = object()


@dataclass(frozen=True)
class AlteracoesDaTarefa:
    """Campos que um PATCH pediu para alterar."""

    titulo: Any = NAO_INFORMADO
    status: Any = NAO_INFORMADO
    prioridade: Any = NAO_INFORMADO
    prazo: Any = NAO_INFORMADO

    def informado(self, campo: str) -> bool:
        return getattr(self, campo) is not NAO_INFORMADO


class UsuarioServico:
    """Operações de cadastro e autenticação de usuários."""

    def __init__(
        self, repositorio: UsuarioRepositorio, hasher: HashDeSenha
    ) -> None:
        self._repositorio = repositorio
        self._hasher = hasher

    def cadastrar(self, nome: str, email: str, senha: str) -> Usuario:
        """Cadastra um usuário com a senha protegida por hash."""

        email = email.strip().lower()

        if self._repositorio.email_existe(email):
            raise EmailJaCadastrado()

        usuario = Usuario(nome=nome, email=email)
        usuario.definir_senha(senha, self._hasher)

        return self._repositorio.salvar(usuario)

    def autenticar(self, email: str, senha: str) -> Usuario:
        """Confere as credenciais e devolve o usuário correspondente."""

        email = email.strip().lower()

        usuario = self._repositorio.buscar_por_email(email)

        if usuario is None or not usuario.senha_confere(
            senha, self._hasher
        ):
            raise CredenciaisInvalidas()

        return usuario

    def buscar(self, usuario_id: int) -> Usuario:
        """Devolve o usuário pelo id."""

        usuario = self._repositorio.buscar_por_id(usuario_id)

        if usuario is None:
            raise UsuarioNaoEncontrado()

        return usuario


class TarefaServico:
    """Operações sobre as tarefas de um usuário."""

    def __init__(
        self, tarefas: TarefaRepositorio, usuarios: UsuarioRepositorio
    ) -> None:
        self._tarefas = tarefas
        self._usuarios = usuarios

    def criar(
        self,
        usuario_id: int,
        titulo: str,
        prioridade: PrioridadeTarefa,
        prazo: date | None,
    ) -> Tarefa:
        """Cria uma tarefa para um usuário existente."""

        if self._usuarios.buscar_por_id(usuario_id) is None:
            raise UsuarioNaoEncontrado()

        tarefa = Tarefa(
            usuario_id=usuario_id,
            titulo=titulo,
            prioridade=prioridade,
            prazo=prazo,
        )

        return self._tarefas.salvar(tarefa)

    def listar(self, filtro: FiltroDeTarefas) -> list[Tarefa]:
        """Lista as tarefas conforme os critérios informados."""
        return self._tarefas.listar(filtro)

    def contar(self, filtro: FiltroDeTarefas) -> int:
        """Conta as tarefas que atendem ao filtro."""
        return self._tarefas.contar(filtro)

    def buscar(self, tarefa_id: int, usuario_id: int) -> Tarefa:
        """Devolve a tarefa somente se pertencer ao usuário informado."""

        tarefa = self._tarefas.buscar_por_id(tarefa_id)

        if tarefa is None:
            raise TarefaNaoEncontrada()

        # CORREÇÃO: verifica se a tarefa pertence ao usuário autenticado.
        if tarefa.usuario_id != usuario_id:
            raise AcessoNaoAutorizado()

        return tarefa

    def atualizar(
        self,
        tarefa_id: int,
        alteracoes: AlteracoesDaTarefa,
        usuario_id: int,
    ) -> Tarefa:
        """Aplica as alterações informadas e devolve a tarefa atualizada."""

        tarefa = self.buscar(tarefa_id, usuario_id)

        if alteracoes.informado("titulo"):
            tarefa.titulo = alteracoes.titulo

        if alteracoes.informado("prioridade"):
            tarefa.prioridade = alteracoes.prioridade

        if alteracoes.informado("prazo"):
            tarefa.prazo = alteracoes.prazo

        if alteracoes.informado("status"):
            tarefa.definir_status(StatusTarefa(alteracoes.status))

        return self._tarefas.salvar(tarefa)

    def remover(self, tarefa_id: int, usuario_id: int) -> None:
        """Remove a tarefa somente se pertencer ao usuário informado."""

        tarefa = self.buscar(tarefa_id, usuario_id)

        self._tarefas.remover(tarefa)
