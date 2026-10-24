# AI Content Automation: Blogs and Social Media Posts (n8n)

An n8n workflow that turns one topic row in Google Sheets into a researched blog post, a Twitter/X thread, a LinkedIn post, a Facebook post and a YouTube script. The blog is written from live web search results and ends with a list of the sources consulted. LinkedIn and Facebook posts are published only after a human approves them by email.

![Workflow canvas](docs/workflow-canvas.png)


## How it works

```mermaid
flowchart TD
  A[Google Sheet: topic row with Status Pending] --> B[Get Pending Topic]
  B --> C[Mark Topic WIP]
  C --> D[Load prompt templates from AI-Prompts sheet]
  D --> E[Inject topic, tone, audience, word count]
  E --> F{WordPress row?}
  F -->|yes| G[Search Web: Tavily, top 5 results]
  G --> H[Generate Blog Post: Gemini with structured schema]
  H --> I[Blog Google Doc plus Sources consulted]
  H --> J[Combine blog with the other prompts]
  F -->|no| J
  J --> K[Generate Platform Content: structured schema]
  K --> L{Route by platform}
  L --> M[Twitter thread Google Doc]
  L --> N[YouTube script Google Doc]
  L --> O[LinkedIn: email approval then post]
  L --> P[Facebook: email approval then post]
  K --> Q[Mark Topic Done]
```

1. A new `Pending` row in the topics sheet (or the manual trigger) starts a run. Only the first `Pending` row is processed per run, and it is marked `WIP`.
2. Prompt templates come from a second sheet tab, so tone and style can change without touching the workflow.
3. **Search first, then write.** Tavily returns the top 5 results for the topic. The blog is written from those results, names the source in the sentence for every fact or number it uses, and the workflow itself appends a "Sources consulted" list built from the real URLs, so links cannot be invented.
4. Gemini writes the blog through an n8n Information Extractor with a JSON schema (`seo_title`, `meta_description`, `blog_content` as HTML). The Google Doc receives clean text, and the disabled WordPress node receives the HTML.
5. A second structured-output step produces the platform content (`thread[]`, `linkedin_post`, `facebook_post`, YouTube `title`, `hook`, `outline[]`, `closing_cta`) and the workflow routes each result to its branch.
6. LinkedIn and Facebook use Gmail "send and wait" double approval with a 2-day timeout. Rejected posts are logged in the sheet and never published.

## Design decisions

- **Structured outputs, not parsing code.** Both AI steps return typed JSON, so the workflow has no regex-based parsing nodes for AI output. Schema rules enforce 5 to 7 tweets and block asterisks in social posts, and the output parser has auto-fix turned on.
- **Human in the loop** for anything that goes public.
- **Grounding rules in the prompt:** facts must come from the sources, numbers must keep their original meaning and name the source, a source that promotes its own product must be labeled, and example scenarios must be introduced as imaginary.
- **Resilience:** retries on the AI and search nodes, and the search step continues with "No sources were found" instead of stopping the run if the search API fails.
- **Safe defaults:** the WordPress and X (Twitter) nodes are disabled in the exported workflow.

## Tech stack

n8n · Google Gemini (blog step) · OpenRouter chat model, tested with `openai/gpt-4o-mini` (platform step) · Tavily Search API · Google Sheets, Docs, Gmail · LinkedIn API · Facebook Graph API · JSON Schema structured output parsers

## Setup

1. In n8n, go to **Workflows → Import from file** and choose `workflow/automate-blogs-and-social-media-posts.json`. Before importing, open the file in a text editor and replace the placeholders:

| Placeholder | Replace with |
|---|---|
| `YOUR_GOOGLE_SHEET_ID` | The ID of your Google Sheet (the long string in its URL) |
| `YOUR_BLOG_DOCS_FOLDER_ID` | Google Drive folder ID for blog Docs |
| `YOUR_TWITTER_DOCS_FOLDER_ID` | Google Drive folder ID for Twitter thread Docs |
| `YOUR_YOUTUBE_DOCS_FOLDER_ID` | Google Drive folder ID for YouTube script Docs |
| `YOUR_LINKEDIN_PERSON_ID` | Your LinkedIn person ID (used by the LinkedIn node) |
| `your-approver@example.com` | The email that receives approval requests |

2. Create a Google Sheet with two tabs named exactly `content-generation-topics` and `AI-Prompts`. Use the files in `sample-data/` as templates (File → Import → **Replace current sheet** for each tab).
3. Create these credentials in n8n and select them on the nodes that show a warning:
   - Google Sheets (and Google Sheets Trigger), Google Docs, Gmail
   - Google Gemini (PaLM) API: for the `Gemini Model - Blog` node
   - OpenRouter API: for the `gpt-4o-mini` node (any chat model that follows JSON schemas can be used)
   - Tavily: a **Header Auth** credential with name `Authorization` and value `Bearer YOUR_TAVILY_KEY`
   - LinkedIn and Facebook Graph API (only needed to publish)
4. Leave the workflow **inactive** while testing. Use the **Manual Test Trigger** with exactly one `Pending` row, and keep the two posting nodes disabled or disapprove the emails.
5. When you are happy with the output, enable the posting nodes and activate the workflow.

## Google Sheet format

**content-generation-topics:** `topic`, `audience`, `tone`, `word_count`, `domain_niche`, `Status`, `linkedin_status`, `facebook_status`

**AI-Prompts:** `Content Platform`, `System Prompt`, `User Prompt`. The `Content Platform` values must be exactly `Wordpress`, `Twitter`, `LinkedIn`, `Facebook` and `YouTube`. Placeholders such as `{{topic}}`, `{{tone}}`, `{{audience}}`, `{{domain_niche}}` and `{{word_count}}` are filled in from the topic row.

To re-run a topic, set `Status` back to `Pending` and clear `linkedin_status` and `facebook_status`. Rows are matched by the `topic` text, so keep topics unique.

## Sample output

See [`docs/sample-output.md`](docs/sample-output.md) for one unedited run (blog, sources, Twitter thread, LinkedIn post, Facebook post and YouTube script).

## Screenshots

**Workflow run**

![Successful execution](docs/execution-success.png)

**Google Sheets control panel**

![Topics sheet](docs/topics-sheet.png)

![Prompt templates](docs/prompts-sheet.png)

**Search and structured output**

![Tavily search results](docs/search-results.png)

![Structured blog output](docs/structured-output.png)

**Generated content and approval**

![Blog Google Doc](docs/blog-doc.png)

![LinkedIn approval email](docs/approval-email-linkedin.png)

![Facebook approval email](docs/approval-email-facebook.png)

![LinkedIn post](docs/linkedin-post.png)

![Facebook post](docs/facebook-post.png)

## Known limitations

- **AI output can still be wrong.** Even with search and grounding rules, the model sometimes adds a detail that no source states or misattributes a fact. This is why the social posts need approval and the blog should be read before it is published.
- **Sources are often vendor blogs.** Search results for tool topics are mostly written by companies that sell the tools. The workflow labels self-promotion, but the sources are still not neutral.
- The blog Google Doc is plain text, so headings are not formatted. The HTML version goes to the (disabled) WordPress node.
- If a Google Sheets node reports a problem with the sheet name after import, pick the tab again from its dropdown.
- The meta description is asked to be about 155 characters but sometimes runs past 160.
- The X (Twitter) node would post only the first tweet of the thread, and it is disabled by default.
- Free tiers have limits. The Gemini preview models occasionally return "Service unavailable", which the retry settings usually absorb, and the Tavily and OpenRouter free plans have monthly or daily caps.
- Execution logs in n8n store the Facebook Page access token returned by the Graph API. Do not share execution data or screenshots of it.

## Author

**Muhammad Tahir** · AI automation and data science
[LinkedIn](https://linkedin.com/in/muhammad-tahir-data)  · [GitHub](https://github.com/mtahir-ds)
