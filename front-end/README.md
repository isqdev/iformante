This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Autenticação opcional

Consulte [o guia de implantação](../back-end/DEPLOY.md) para as variáveis,
migrações, armazenamento de PDFs e preparação das chamadas em produção.

O FastAPI controla cadastro institucional, confirmação por código, sessões e recuperação. No Next configure somente `BACKEND_API_URL`, conforme `.env.example`.

No ambiente do back-end configure `AUTH_SECRET` (segredo aleatório de pelo menos 32 caracteres), `APP_PUBLIC_URL`, `SMTP_HOST`, `SMTP_FROM` e as credenciais SMTP. Consulte `back-end/.env.example`. Em HTTPS use `COOKIE_SECURE=true`. Nenhum segredo deve receber prefixo `NEXT_PUBLIC_`.

Depois de aplicar as migrações, execute `python -m scripts.configure_retention` no back-end. O Neon exige configurar `cron.database_name` para o banco da aplicação e reiniciar o compute antes da instalação; o job usa 03:00 UTC (00:00 em São Paulo) e depende de compute ativo. A API bloqueia chats vencidos mesmo antes da limpeza.

A conta especial é provisionada pelo script `python -m scripts.provision_admin`, que solicita a senha pelo terminal e preserva senhas já provisionadas.

### Verificação

- `npm run build` e `npm run lint`.
- Com o front em `localhost:3001`, `npx playwright test`: telas de conta, documentos e PDF em 320, 390, 768 e 1440 px. Serviços externos são simulados nesses testes.
- No back-end, `python -m unittest tests.test_optional_auth`: integração com transações revertidas, sem enviar mensagens de e-mail.

Ao arrastar fontes externas, alguns navegadores ocultam nome/URL até o drop. A sobreposição aparece somente quando o conteúdo pode ser validado durante o arraste; conteúdos ocultos são validados ao soltar.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
