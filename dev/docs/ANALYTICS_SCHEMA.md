# BIM Standards Chat Analytics - Data Schema Documentation

## Overview
This document describes the data structure for chat analytics logs from the BIM Standards Chat application. The data is stored in JSONL (JSON Lines) format where each line represents a single message exchange.

## File Structure
```
/ChatLogs/
├── 2025-12-10_nrackard_2025-12-10_09-42-17.json
├── 2025-12-10_jdoe_2025-12-10_14-23-01.json
└── screenshots/
    ├── 2025-12-10_09-42-17_2025-12-10T14-44-37-945000.png
    └── 2025-12-10_14-23-01_2025-12-10T14-25-10-123000.png
```

## Schema Definition v3 (With Token Tracking)

```json
{
  "session_id": "2025-12-10_09-42-17",
  "timestamp": "2025-12-10T14:44:37.945000",
  "username": "nrackard",
  "model_name": "Tower_A_Renovation",
  "view_name": "L2 - Floor Plan",
  "query": "How do I fix the line weights in this view?",
  "response": "According to our Line Weight Standards...",
  "source_count": 2,
  "source_urls": [
    "https://company.sharepoint.com/sites/BIM/Standards/LineWeights.aspx",
    "https://company.sharepoint.com/sites/BIM/Standards/ViewTemplates.aspx"
  ],
  "selection_count": 5,
  "duration_seconds": 3.42,
  "input_tokens": 2450,
  "output_tokens": 380,
  "total_tokens": 2830,
  "has_screenshot": true,
  "screenshot_path": "N:\\ChatLogs\\screenshots\\2025-12-10_09-42-17_2025-12-10T14-44-37-945000.png"
}
```

## Field Descriptions

| Field | Type | Description | Example |
|:------|:-----|:------------|:--------|
| `session_id` | String | Unique identifier for the conversation thread | `"2025-12-10_09-42-17"` |
| `timestamp` | ISO 8601 String | UTC timestamp when the interaction occurred | `"2025-12-10T14:44:37.945000"` |
| `username` | String | Revit username of the person chatting | `"nrackard"` |
| `model_name` | String | Name of the Revit project file open at the time | `"Tower_A_Renovation"` |
| `view_name` | String | The specific view active in Revit | `"L2 - Floor Plan"` |
| `query` | String | The raw text of the question asked | `"How do I fix line weights?"` |
| `response` | String | The full AI-generated response text | `"According to our standards..."` |
| `source_count` | Integer | Number of documentation pages cited | `2` |
| `source_urls` | Array[String] | URLs of the cited standards documents | `["https://..."]` |
| `selection_count` | Integer | Number of Revit elements selected when asking | `5` |
| `duration_seconds` | Float | Time taken for the AI to respond (seconds) | `3.42` |
| `input_tokens` | Integer | **NEW** - Tokens in the input (query + context + history) | `2450` |
| `output_tokens` | Integer | **NEW** - Tokens in the AI's response | `380` |
| `total_tokens` | Integer | **NEW** - Sum of input + output tokens | `2830` |
| `has_screenshot` | Boolean | Whether a screenshot was included | `true` |
| `screenshot_path` | String | Absolute path to the screenshot file (if exists) | `"N:\\...\\screenshot.png"` |

## Token Metrics Explained

### What are tokens?
Tokens are the units that language models (like Claude) use to process text. Roughly:
- 1 token ≈ 0.75 words in English
- 100 tokens ≈ 75 words or ~1 paragraph

### Token Composition

**Input Tokens** include:
- User's query
- All cited standards content (from SharePoint/Notion)
- Conversation history (previous messages)
- Revit context metadata
- Screenshot (if included - images consume many tokens)

**Output Tokens** include:
- The AI's text response
- Formatted markdown/bullets

### Why Track Tokens?

1. **Cost Analysis**: Anthropic charges based on tokens
   - Claude Sonnet 3.5: ~$3 per million input tokens, ~$15 per million output tokens
   - Formula: `cost = (input_tokens * $0.000003) + (output_tokens * $0.000015)`

2. **Performance Insights**:
   - High input tokens = Large context (many standards cited)
   - High output tokens = Detailed response
   - Token/duration ratio = Response generation speed

3. **Optimization Opportunities**:
   - Identify queries that pull in too much context
   - Optimize standards document length
   - Track conversation history impact

## Dashboard Metrics to Build

### Cost Analytics
- **Total Cost**: `SUM(input_tokens * 0.000003 + output_tokens * 0.000015)`
- **Cost by User**: Group by username
- **Cost by Project**: Group by model_name
- **Average Cost per Query**: Total cost / interaction count

### Token Efficiency
- **Average Input Tokens**: `AVG(input_tokens)`
- **Average Output Tokens**: `AVG(output_tokens)`
- **Token Distribution**: Histogram of total_tokens
- **Input/Output Ratio**: `AVG(input_tokens / output_tokens)`

### Performance Correlation
- **Tokens vs Duration**: Scatter plot showing correlation
- **Tokens per Source**: `AVG(input_tokens / source_count)` - How much context per standard?
- **Response Quality**: High output tokens might indicate detailed answers

### Trends Over Time
- **Daily Token Usage**: Line chart of total_tokens over time
- **Cost Trend**: Daily/weekly/monthly cost projections
- **User Adoption Impact**: Token growth as more users adopt the tool

## PowerBI Data Import

1. **Get Data** > **Folder**
2. Point to: `N:\Design Technology Resources\00_Admin\ChatLogs`
3. **Transform Data**:
   - Filter to `.json` files only
   - **Add Column** > **Custom Column**: 
     ```powerquery
     Json.Document([Content])
     ```
   - **Expand** the JSON column to individual fields
4. **Add Calculated Column** for cost:
   ```powerquery
   ([input_tokens] * 0.000003) + ([output_tokens] * 0.000015)
   ```

## Example Queries

### Find Expensive Queries
```sql
SELECT username, query, total_tokens, 
       (input_tokens * 0.000003 + output_tokens * 0.000015) as cost_usd
FROM logs
ORDER BY cost_usd DESC
LIMIT 10
```

### User Cost Ranking
```sql
SELECT username, 
       COUNT(*) as query_count,
       AVG(total_tokens) as avg_tokens,
       SUM(input_tokens * 0.000003 + output_tokens * 0.000015) as total_cost_usd
FROM logs
GROUP BY username
ORDER BY total_cost_usd DESC
```

### Token Efficiency by Source Count
```sql
SELECT source_count,
       AVG(input_tokens) as avg_input,
       AVG(output_tokens) as avg_output,
       AVG(duration_seconds) as avg_duration
FROM logs
GROUP BY source_count
ORDER BY source_count
```
