# Implantação em produção

## Configuração

Use `back-end/.env.example` como referência para as variáveis do servidor.
Configure `DATABASE_URL`, as chaves OpenAI e Groq, um `AUTH_SECRET` aleatório
com pelo menos 32 caracteres e as credenciais SMTP. Defina `APP_PUBLIC_URL`
com a origem HTTPS do frontend, sem caminhos, e `COOKIE_SECURE=true`.

No frontend configure `BACKEND_API_URL` com a URL do backend. Chaves e
credenciais ficam exclusivamente no servidor. Não versione arquivos `.env`.

Mantenha os PDFs originais em armazenamento persistente e configure
`DOCUMENT_STORAGE_DIR` para esse diretório. Em produção deixe
`DOCUMENT_REMOTE_BASE_URL` vazio; essa opção serve ao ambiente local.

## Preparação e publicação

1. Faça backup do banco e dos PDFs antes de aplicar as migrações. A migração
   de autenticação cria um índice único em `lower(email)`; resolva eventuais
   contas existentes com e-mails duplicados antes de executá-la.
2. No diretório `back-end`, instale as dependências e aplique as migrações
   antes de iniciar a nova versão:

   ```sh
   uv sync --frozen --no-dev
   uv run alembic upgrade head
   ```

3. O Dockerfile instala automaticamente a voz `pt_BR-faber-medium`. Se não
   usar Docker, execute `uv run python scripts/install_call_voice.py`.
   Os arquivos ONNX e JSON são baixados e verificados pelo script, sem
   necessidade de enviá-los ao Git. Consulte `voices/NOTICE.md`.
4. Inicie a API com um processo e uma réplica para que a síntese e o
   cancelamento de chamadas compartilhem o mesmo estado:

   ```sh
   uv run uvicorn app.app:app --host 0.0.0.0 --port 8000 --workers 1
   ```

5. No diretório `front-end`, execute `npm ci`, `npm run build` e
   `npm run start`, ou use os comandos equivalentes do provedor.
   Preserve o streaming nas rotas de chat e chamada, sem buffering no proxy.

## Operações após as migrações

- Para provisionar a conta administrativa inicial, execute
  `uv run python -m scripts.provision_admin`. A senha é solicitada no terminal.
- Configure `pg_cron` no banco e execute
  `uv run python -m scripts.configure_retention` para a limpeza diária.
  A função remove conversas vencidas após sete dias e registros de
  autenticação expirados. O script verifica a configuração do provedor.
- Para recalcular destaques de PDFs já indexados, execute
  `uv run python -m scripts.backfill_pdf_anchors` com os arquivos originais
  disponíveis. Não é necessário gerar embeddings novamente.

## Conferência

Verifique o acesso ao chat temporário, login, documentos e fontes em PDF.
Em `/call`, permita o microfone e confirme gravação, transcrição e reprodução.
O endpoint `/call/status` informa a disponibilidade da configuração.
Chamadas permanecem temporárias, inclusive para usuários autenticados.

Logs locais, avaliações, prévias de design, modelos baixados e planos de
implementação não são necessários para publicar a aplicação.
