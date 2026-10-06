# Agent Prompt Template

Build cron prompts quickly using this structure.

## Structure

```
## Input Format
[Describe the JSON/CSV/text structure your script outputs]
Example: JSON with {search_term, context, products: [{title, price, url}]}

## Task
For EACH item in data:

### 1. ANALYZE
[Specify scoring logic and criteria]
Example: Score 0-100 if product matches context (price range, category, condition).

### 2. FILTER
[Keep only items scoring >= threshold]
Example: Keep only products with >=60% confidence.

### 3. SEND
[Format and delivery instructions]
Example: Send ONE Telegram message per product with: title (bold), [link](url), price + store, reasoning.

## Output
Send messages to [service]. Print nothing to stdout. Errors to stderr.
```

## Example: Product Hunting

```
Input: JSON with searched products {title, price, store, url, category}.

For EACH product:
  1. ANALYZE: Score 0-100 if matches context (price reasonable? category right? condition acceptable?)
  2. FILTER: Keep >=60% confidence
  3. SEND: ONE Telegram message per product
     Format: **title** | [View](url) | Price + Store | Reasoning

Output: Messages to Telegram. Nothing to stdout. Errors to stderr.
```

## Example: News Monitoring

```
Input: JSON with {company_name, articles: [{title, url, source, date}]}

For EACH article:
  1. ANALYZE: Is this material news (affects stock/reputation/strategy)? Score 0-100.
  2. FILTER: Keep >=70% confidence (news only, not rumors)
  3. SEND: ONE Slack message per article
     Format: :newspaper: **[Company]** | [Title](url) | Source | Your assessment

Output: Messages to Slack. Nothing to stdout. Errors to stderr.
```

## Multiple Individual Messages: Use `---` Delimiters

When you need N separate deliveries (one message per product, one message per alert), use `---` block separators. Hermes cron gateway splits on these delimiters automatically.

```
For each matched product, output:
---
{product_title}
{product_url}
{price} | {store}
Confidence: {score}/100
---

Then blank line before next product.
```

Each `---` block becomes one separate Telegram message. No need for loops or API calls in the prompt — the cron gateway handles splitting.

**Pitfall:** If you write `--prompt="send one message per product"` without `---` delimiters, all products will be batched into one message. The words "separate message" have no effect on the gateway — only `---` delimiters cause splitting.

## Keys to Good Prompts

- **Explicit structure**: Agent sees exactly what fields are in the input
- **Clear decision rules**: What does "match" mean? Numeric threshold preferred
- **Output format per service**: Telegram uses markdown, Slack uses blocks, email is plain text
- **One message per item or batch?** State it clearly (if multiple, use `---` delimiters)
- **Silent delivery**: Nothing to stdout so cron logs stay clean
