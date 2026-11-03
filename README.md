# JP Invoice Check — Japanese qualified invoice checker for AI agents (MCP)

Checks a Japanese qualified invoice (適格請求書) before an agent sends or accepts it:

- the six items the National Tax Agency requires (issuer name + registration number, date, description with reduced-rate marks, total per tax rate, tax per tax rate, buyer name)
- consumption tax rounded **once per invoice per rate**, not per line. Summing per-line rounded tax is a common agent mistake; the checker returns it as a named error (code, field, English and Japanese message)
- the format and check digit of the registration number (T + 13 digits). It does not look up whether the number is currently registered.

Deterministic. Python standard library only. The invoice is not stored or sent anywhere.

## Connect (MCP, streamable HTTP)

This Actor runs in Standby mode. Use the MCP URL that Apify shows on this Actor's page (Standby URL + `/mcp`) with your Apify API token, in any MCP client that supports remote servers.

Tools:

| Tool | What it does | Charged |
|---|---|---|
| `jp_invoice_check` | Full check of one invoice (`role`: `issue` for invoices you send, `receive` for a supplier's) | yes, event `invoice-checked` |
| `jp_invoice_tax` | Tax for one rate on one invoice (floor / half_up / ceil, exclusive / inclusive) | no |
| `jp_invoice_registration_number` | Normalize and check a registration number | no |
| `jp_invoice_checker_info` | Version and sha256 of the checking code | no |

Only successful `jp_invoice_check` calls are charged. Errors and the other tools are free.

## Run it yourself for free

The same checker is open source (MIT): https://github.com/japan-ai-tools/jp-invoice-check

```
pip install jp-invoice-check        # stdio MCP server: jp-invoice-check
python -m jpinvoice.http_server     # MCP over HTTP on 127.0.0.1:8765/mcp (from the GitHub source)
```

## Network

The only outgoing call is Apify's own charge API (`POST https://api.apify.com/v2/actor-runs/{runId}/charge`, https://docs.apify.com/api/v2/post-charge-run), made from inside the Apify run after a successful `jp_invoice_check`. It sends the event name, the count (1) and Apify's request id, never the invoice. Outside Apify (no `ACTOR_RUN_ID` / `APIFY_TOKEN`) nothing is sent anywhere. No web pages are fetched.

## Limits

- It checks the invoice you send it. It does not read PDFs or images; pass the fields as JSON.
- It is a checking tool, not tax advice. Rules: National Tax Agency leaflet on qualified invoices (https://www.nta.go.jp/publication/pamph/shohi/shohizei_11.pdf).

---

## 日本語

AIエージェントが請求書を出す前・受け取る前に、適格請求書の記載事項6つと「税率ごとに1回」の端数処理を検査する MCP サーバーです。品目ごとに丸めた税を足す誤りを、名前つきで返します。登録番号は形と検査用数字だけを確かめます(登録の有無は照会しません)。

- 課金されるのは `jp_invoice_check` が成功したときだけ(イベント名 `invoice-checked`)。ほかの道具とエラーは無料です
- 同じ道具は GitHub と PyPI で無料(MIT)。自分のPCで動かせます
- 税の助言ではありません
