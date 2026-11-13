# Jane Cabeleireira Hair — Sistema de Agendamentos

Aplicação completa: página de cadastro + banco de dados (SQLite) + confirmação automática por WhatsApp.

## Como executar

```bash
pip install -r requirements.txt
python3 server.py
```

Abra **http://localhost:5000** no navegador.

- Página de cadastro: `http://localhost:5000/`
- Lista de agendamentos: `http://localhost:5000/agendamentos`
- API JSON: `GET http://localhost:5000/api/agendamentos`

## Banco de dados

O arquivo `agendamentos.db` (SQLite) é criado automaticamente na primeira execução.
Tabela `agendamentos`:

| Campo            | Tipo    | Descrição                                  |
|------------------|---------|--------------------------------------------|
| id               | INTEGER | chave primária auto-incremento             |
| nome_cliente     | TEXT    | nome do cliente                            |
| telefone         | TEXT    | telefone em formato internacional (ex.: 5581999999999) |
| data_hora        | TEXT    | data/hora ISO (YYYY-MM-DDTHH:MM)           |
| servico          | TEXT    | serviço selecionado (opcional)             |
| criado_em        | TEXT    | data/hora do cadastro                      |
| status           | TEXT    | `agendado` (padrão)                        |
| whatsapp_enviado | INTEGER | 1 = enviado / 0 = falhou                   |
| whatsapp_erro    | TEXT    | mensagem de erro (ou "mock")               |

Para consultar manualmente: `sqlite3 agendamentos.db "SELECT * FROM agendamentos;"`

## WhatsApp — configuração

Por padrão o sistema roda em **modo MOCK**: ele não envia mensagens de verdade, apenas imprime no console o que seria enviado e marca como "mock" no banco. Use esse modo para testar a página e o banco.

### Opção 1 — API Oficial (Meta Cloud API) — recomendada

É a forma oficial (não bloqueia o número). Custa nada para até 1.000 conversas por mês.

1. Acesse https://developers.facebook.com/ e crie uma conta de desenvolvedor.
2. Crie um App do tipo **Negócios** → adicione o produto **WhatsApp**.
3. No painel do WhatsApp (menu "Começar"), copie:
   - **Token de acesso temporário** (ACCESS_TOKEN)
   - **ID do número de telefone** (PHONE_NUMBER_ID)
4. Adicione o número do cliente (destinatário) na lista de destinatários de teste.
5. Execute o servidor com as variáveis:

```bash
WHATSAPP_PROVIDER=meta \
WHATSAPP_TOKEN="seu_token_aqui" \
WHATSAPP_PHONE_NUMBER_ID="seu_phone_number_id" \
python3 server.py
```

**Importante:** mensagens iniciadas pelo salão (sem o cliente ter escrito antes) exigem um **template de mensagem aprovado** pela Meta. O texto livre só funciona dentro da janela de 24h após o cliente mandar mensagem para o seu número. Para testar, mande uma mensagem do número do cliente para o número do salão primeiro (abre a janela de 24h). Para produção, crie um template de confirmação na área "Gestor de mensagens" e adapte o payload em `server.py` (`enviar_whatsapp_meta`).

### Opção 2 — Evolution API / Z-API / Twilio (alternativas comuns no Brasil)

São gateways que também usam a API oficial ou conectam um número real. A lógica é a mesma: basta trocar a função `enviar_whatsapp_meta` em `server.py` pelo endpoint do seu provedor (todos são REST com token). O campo `telefone` já vem normalizado em formato internacional.

- **Evolution API** (open-source, self-hosted): `POST {URL}/message/sendText/{instancia}` com header `apikey`.
- **Twilio WhatsApp**: usa `https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json` com auth básico.
- **Z-API**: `POST https://api.z-api.io/instances/{id}/token/{token}/send-text`.

> ⚠️ Evite bibliotecas não oficiais que emulam o WhatsApp Web (ex.: whatsapp-web.js, Baileys) em número próprio: violam os termos da Meta e o número pode ser banido.

## Estrutura do projeto

```
jane-salon/
├── cadastro-atendimento.html   # página (front-end, servida em /)
├── server.py                   # backend Flask + banco + WhatsApp
├── agendamentos.db             # banco SQLite (criado automaticamente)
├── requirements.txt
└── README.md
```

## Personalização

- **Mensagem do WhatsApp:** edite a função `montar_mensagem()` em `server.py`.
- **Serviços do select:** edite as `<option>` em `cadastro-atendimento.html`.
- **Cores/visual:** variáveis no bloco `:root` do CSS em `cadastro-atendimento.html`.
