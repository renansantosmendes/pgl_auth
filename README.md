# pgl_auth

Pacote Python para autenticação de alunos (matrícula + senha) e emissão de um token JWT
de curta duração (4 horas) para acesso ao proxy dos modelos de IA usado na disciplina.

## Componentes deste repositório

- `src/pgl_auth/` — pacote publicado no PyPI, instalado pelos alunos (`pip install pgl-auth`).
- `api/login.py` — API serverless (FastAPI) hospedada no Vercel, valida matrícula/senha no
  Postgres e emite o JWT. Nenhuma credencial do banco fica no pacote instalado pelos alunos.
- `db/schema.sql` — schema `pgl_auth` e tabela `pgl_auth.students`.
- `db/migrate.py` — aplica `schema.sql` no banco (usa `NEON_DATABASE_URL` do `.env`).
- `db/create_student.py` — cria/atualiza a senha de um aluno (hash bcrypt).
- `.github/workflows/publish.yml` — CI que publica o pacote no PyPI a cada release do GitHub.

## Uso pelo aluno

```bash
pip install pgl-auth
```

```python
from pgl_auth import PGLAuthClient

client = PGLAuthClient()  # usa PGL_AUTH_API_URL ou o default do Vercel
token = client.login("2021012345", "minha_senha")

# usar o token para chamar o proxy dos modelos
headers = client.auth_header()  # {"Authorization": "Bearer <token>"}
```

Ou via linha de comando:

```bash
pgl-auth 2021012345
```

## Estrutura da tabela `pgl_auth.students`

| coluna          | tipo          | descrição                                   |
|------------------|---------------|----------------------------------------------|
| `id`             | UUID (PK)     | identificador único, gerado automaticamente   |
| `matricula`      | TEXT (UNIQUE) | matrícula do aluno                            |
| `password_hash`  | TEXT          | hash bcrypt da senha (nunca texto puro)       |
| `is_active`      | BOOLEAN       | se o aluno pode autenticar                    |
| `updated_at`     | TIMESTAMPTZ   | atualizado automaticamente via trigger         |

## Provisionar o banco

```bash
pip install -e ".[admin]"
python db/migrate.py                 # cria schema + tabela
python db/create_student.py 2021012345   # cadastra/atualiza um aluno (pede a senha)
```

## Testes

```bash
pip install -e ".[dev]"
pytest
```

`tests/test_create_student.py` garante as regras de negócio do cadastro de senha
(bloqueio se a matrícula não existir ou estiver inativa em `pgl_proxy.students`,
e overwrite do registro existente em `pgl_auth.students`). `tests/test_client.py`
cobre o cliente HTTP usado pelos alunos. Os testes rodam com dependências
mockadas — não tocam no banco real — e são executados automaticamente no CI
antes de qualquer build/publish (job `test` em `publish.yml`).

## Deploy da API no Vercel

1. Importe este repositório no Vercel (Project → Add New → Project).
2. Configure as variáveis de ambiente do projeto no Vercel:
   - `NEON_DATABASE_URL`
   - `JWT_SECRET_KEY`
3. Deploy automático a cada push — o Vercel detecta `api/login.py` automaticamente e cria
   a função serverless em `/api/login`. As dependências da função ficam em `requirements.txt`
   **na raiz do projeto** (a Vercel só lê o `requirements.txt` da raiz, não um dentro de `api/`).
   Não é preciso `vercel.json`; declarar `runtime` manualmente lá costuma quebrar com
   "Function Runtimes must have a valid version" se a versão não for pinada. Como agora a
   raiz também tem o `pyproject.toml` do pacote PyPI, é preciso apontar o entrypoint da
   função explicitamente — já configurado em `[tool.vercel]` no `pyproject.toml`.
4. Atualize `DEFAULT_API_URL` em `src/pgl_auth/client.py` (ou oriente os alunos a definir
   `PGL_AUTH_API_URL`) com a URL final do deploy.

## Publicar o pacote no PyPI

O workflow `.github/workflows/publish.yml` roda a cada push na `main` (também em
release/`workflow_dispatch`): testa, builda e publica no PyPI usando um **API token**
guardado como secret do repositório.

Configuração única (uma vez só):

1. pypi.org → Account settings → API tokens → **Add API token**.
   - Se o projeto `pgl-auth` ainda não existe no PyPI, crie o token com escopo
     "Entire account" (o escopo pode ser restrito ao projeto depois do primeiro publish).
2. No GitHub: repo → Settings → Secrets and variables → Actions → **New repository secret**.
   - Nome: `PYPI_API_TOKEN`
   - Valor: o token gerado no passo anterior (começa com `pypi-`).
3. Pronto — o job `publish` usa `secrets.PYPI_API_TOKEN` automaticamente.

`skip-existing: true` faz o publish ser ignorado (sem falhar o job) quando a versão em
`pyproject.toml` já foi publicada antes, então pushes na main sem bump de versão não
quebram o CI.

Para publicar uma nova versão:

```bash
# atualizar version em pyproject.toml
git tag v0.1.0 && git push origin v0.1.0
# criar uma Release no GitHub a partir dessa tag -> dispara o workflow
```
