# Intro

👋 We’re delighted you’re considering contributing your forecasts to ForecastBench! This page details the steps required to ensure they’re successfully included in the benchmark.

Some participants have decided to share their forecasting code. Feel free to [peruse their repositories](Open-source-participants), both for forecasting strategies and to find code that might speed the development of the code for your submission.


## TL;DR
1. [Contact us](How-to-submit-to-ForecastBench#1-contact-us)
1. [Download the Question Set](How-to-submit-to-ForecastBench#3-download-the-question-set) at 0:00 UTC on the forecast due date
1. Generate your [Forecast Set](How-to-submit-to-ForecastBench#4-forecast-set)
1. [Upload your Forecast Set](How-to-submit-to-ForecastBench#6-submit) by 23:59:59 UTC on the forecast due date

# 1. Contact Us

To participate, a team must contact [forecastbench@forecastingresearch.org](mailto:forecastbench@forecastingresearch.org) with the list of email addresses that should be allowed to upload their team's forecasts. If you'd like to [submit anonymously](How-to-submit-to-ForecastBench#61-anonymous-submissions), please specify that too.

In response, they'll be provided
1. a folder on a GCP Cloud Storage bucket to which they should upload their forecast set, and
1. the next _forecast due date_ (every two weeks starting 2025-03-02).
1. if submitting anonymously, your anonymous organization name.

💡 When you receive the response email, ensure you can log into GCP and upload a test file to your bucket to ensure the process goes smoothly. Feel free to reach out with any followup questions.

# 2. Prepare your code

Ensure your code runs correctly _before_ the forecast due date. 

Follow the steps below using a [previously-released question set](https://github.com/forecastingresearch/forecastbench-datasets/tree/main/datasets/question_sets) to ensure you know how to successfully create a forecast set. 

ℹ️ Question sets generated before `2025-10-26` contained combination questions, as described in the paper. To test your setup for rounds starting `2025-10-26` and later:
  * read in the `"questions"` array from the old question set
  * remove the combination questions before proceeding
    * combination questions have an array value for the "id" field.

ℹ️ Unfortunately, we won't always be able to respond to emails on the forecast due date, so it would be best to ensure your code works well beforehand.

⚠️ For your model to be included on the leaderboard, it _must_ provide the requested forecasts for at least 95% of market questions and at least 95% of dataset questions.

⚠️ Any missing forecasts will be imputed a forecast value of $0.5$.

# 3. Download the question set

At **0:00 UTC on the _forecast due date_**, navigate to https://github.com/forecastingresearch/forecastbench-datasets/tree/main/datasets/question_sets to download the latest question set. The question set will be named like `<<forecast_due_date>>-llm.json`.

⚠️ NB We are working on getting the question set released exactly at 0:00 UTC, though VM startup times on our cloud provider are not consistent and so this can result in delays of publishing the question set of up to 5 minutes. This means you should see question set by 0:05 UTC at the latest.

## Question set data dictionary

The question set is of the format:
```json
{
    "forecast_due_date": {
        "description": "Date in ISO format. e.g. 2024-07-21. Required.",
        "type": "string"
    },
    "question_set": {
        "description": "The name of the file that contains the question set. e.g. 2024-07-21-llm.json. Required.",
        "type": "string"
    },
    "questions": {
        "description": "A list of questions to forecast on. Required.",
        "type": "array<object>"
    }
}
```
There are $500$ questions in the `"questions"` array: $250$ market questions and $250$ dataset questions. Each question is described by the data dictionary below. 

```json
{
    "id": {
        "description": "A unique identifier string given `source`. Required.",
        "type": "string"
    },
    "source": {
        "description": "Where the data comes from. e.g. 'acled'. Required.",
        "type": "string"
    },
    "question": {
        "description": "For questions sourced from 'market' sources, this is just the original question. For 'dataset' questions, this is the question presented as a Python f-string with the placeholders `{forecast_due_date}` and `{resolution_date}`. For the human survey, `{resolution_date}` may be replaced by 'the resolution date' while `{forecast_due_date}` may be replaced by 'the forecast due date' or 'today'. For LLMs, this template allows flexibility in deciding what information to insert (e.g. ISO date, date in the format of your choosing, or human replacements above). Required.",
        "type": "string"
    },
    "resolution_criteria": {
        "description": "ForecastBench resolution criteria. Specifies how forecasts will be evaluated for each question type. e.g. 'Resolves to the value calculated from the ACLED dataset once the data is published.' Required.",
        "type": "string"
    },
    "background": {
        "description": "Background information about the forecast question provided by the source, if available. Default: 'N/A'",
        "type": "string"
    },
    "market_info_open_datetime": {
        "description": "The datetime when the forecast question went on the market specified by `source`. e.g. 2022-05-02T05:00:00+00:00. Default: 'N/A'",
        "type": "string"
    },
    "market_info_close_datetime": {
        "description": "The datetime when the forecast question closes on the market specified by `source`. e.g. 2022-05-02T05:00:00+00:00. Default: 'N/A'",
        "type": "string"
    },
    "market_info_resolution_criteria": {
        "description": "The resolution criteria provided by the market specified by `'source'`, if available. Default: 'N/A'",
        "type": "string"
    },
    "url": {
        "description": "The URL where the resolution value is found. e.g. 'https://acleddata.com/'. Required.",
        "type": "string"
    },
    "freeze_datetime": {
        "description": "The datetime UTC when this question set was generated. This will be 10 days before the forecast due date. e.g. 2024-07-11T00:00:00+00:00. Required.",
        "type": "string"
    },
    "freeze_datetime_value": {
        "description": "The latest value of the market or comparison value the day the question was frozen. If there was an error, it may be set to 'N/A'. e.g. '0.25'. Required.",
        "type": "string"
    },
    "freeze_datetime_value_explanation": {
        "description": "Explanation of what the value specified in `value_at_freeze_datetime` represents. e.g. 'The market value.' Required.",
        "type": "string"
    },
    "source_intro": {
        "description": "A prompt that presents the source of this question, used in the human survey and provided here for completeness. Required.",
        "type": "string"
    },
    "resolution_dates": {
        "description": "The resolution dates for which forecasts should be provided for this forecast question. Only used for dataset questions. 'N/A' value for market questions. e.g. ['2024-01-08', '2024-01-31', '2024-03-31', '2024-06-29', '2024-12-31', '2026-12-31', '2028-12-30', '2033-12-29']. Required.",
        "type": "array<string> | string"
    }
}
```

## Read the question set (helpful snippet)

After downloading the question set, read in the questions:
```python
import json
import pandas as pd

question_set_filename = "2024-07-21-llm.json"
with open(question_set_filename, "r", encoding="utf-8") as f:
    question_set = json.load(f)

forecast_due_date = question_set["forecast_due_date"]
question_set_name = question_set["question_set"]
df = pd.DataFrame(question_set["questions"])

assert len(df) == 500
```

You have 24 hours to generate and upload your forecasts for this question set.

# 4 Forecast set

A forecast set is the ensemble of all of your forecasts on a question set, and what we use to score your forecasting performance. 

## 4.1 Forecast set name

Your uploaded forecast set should be a JSON file named like `<<forecast_due_date>>.<<organization>>.<<N>>.json`, where:
* `forecast_due_date` is the forecast due date associated with the question set (`forecast_due_date` from the [snippet above](How-to-submit-to-ForecastBench#read-the-question-set-helpful-snippet))
* `organization` is your organization's name
* `N` is the number of this forecast set; only important if you submit more than one forecast set per forecast due date. 
  * ⚠️ You may submit up to $3$ forecast sets per round. If you submit more than $3$, we will only consider the first $3$ files in alphabetical order.


## 4.2 Forecast set data dictionary

Your forecast set should contain the 5 keys defined by the following data dictionary:
```json
{
    "organization": "<<your organization>>",
    "model": "<<the model you're testing; if ensemble of models, write 'ensemble'; if submitting multiple forecasts with the same model, then differentiate them here (e.g. '(prompt 1)')>>",
    "model_organization": "<<the organization that created the model; if ensemble, this should contain the same value as `organization`.>>",
    "question_set": "<<'question_set' from the question set file.>>",
    "forecasts": [
        {}
    ]
}
```
The keys `organization` and `model_organization` will be used to find the appropriate logo for the leaderboard. The key `model` will appear directly on the leaderboard as written here.

⚠️ If submitting anonymously, use the organization name provided for both `organization` and `model_organization`.

⚠️ The value provided for `model` must be accurate on submission and may not be changed after results are posted.

`question_set` contains the value of `question_set` from the question set file (`question_set_name` from the [snippet above](How-to-submit-to-ForecastBench#read-the-question-set-helpful-snippet)).

The forecasts are contained in an array of JSON objects under the `forecasts` key. Each JSON object in the array represents a single forecast and is defined by the following data dictionary:
```json
{
    "id": {
        "description": "A unique identifier string given `source`, corresponding to the `id` from the question in the question set that's being forecast. e.g. 'd331f271'. Required.",
        "type": "string"
    },
    "source": {
        "description": "The `source` from the question in the question set that's being forecast. e.g. 'acled'. Required.",
        "type": "string"
    },
    "forecast": {
        "description": "The forecast. A float in [0,1]. e.g. 0.5. Required.",
        "type": "number"
    },
    "resolution_date": {
        "description": "The resolution date this forecast corresponds to. e.g. '2025-01-01'. `null` for market questions. Required.",
        "type": "string | null"
    },
    "reasoning": {
        "description": "The rationale underlying the forecast. e.g. ''. Optional.",
        "type": "string | null"
    },
}
```

# 5. Forecasts

There are two _question types_ in the question set:
1. market: questions sourced from forecasting platforms
1. dataset: questions generated from time series

The number of forecasts to provide depends on both the _type_ and is summarized in the table below.

|         | Standard |
| ------- | -------- |
| Market  | [1](./How-to-submit-to-ForecastBench#511-standard-market-questions-1-forecast) |
| Dataset | $\le$ [8](How-to-submit-to-ForecastBench#512-standard-dataset-questions--8-forecasts) |

The links above take you directly to the sections explaining why that number of forecasts are required. In short:
* Market question: 1 forecast of the final outcome ($1$ forecast)
* Dataset question: 1 forecast at each of 8 resolution dates ($\le8$ forecasts)
* NB: $\le$ for dataset questions because if a series updates less frequently than weekly we'll have 7 resolution dates for that series.

⚠️ Contrary to what is written in the paper, we are _not_ scoring unresolved market questions; we now wait until the questions resolve before scoring them. This is because scoring the unresolved questions dampened the signal we got from the scores on resolved questions.

## Differentiate between question types (helpful snippet)

To differentiate between __question types__: check to see whether the `"source"` is a market source or a dataset source.
```python
SOURCES = {
    "market": ["infer", "manifold", "metaculus", "polymarket"],
    "dataset": ["acled", "dbnomics", "fred", "wikipedia", "yfinance"],
}

# question source masks
market_mask = df["source"].isin(SOURCES["market"])
dataset_mask = df["source"].isin(SOURCES["dataset"])

df_market = df[market_mask]
df_dataset = df[dataset_mask]

assert len(df_market) == 250
assert len(df_dataset) == 250
assert df[~market_mask & ~dataset_mask].empty
```

## 5. Questions

The forecasting questions in ForecastBench are binary questions that ask how likely it is that a given event will (or will not) occur by a specified date.

### 5.1 _Market_ questions: 1 forecast

For every question in `df_market` from the [snippet above](How-to-submit-to-ForecastBench#differentiate-between-question-types-and-sources-helpful-snippet), you should provide your model's forecast of the final outcome of the question.

👀 An example forecast for a market question would look like:
```json
{
    "id": "14364",
    "source": "metaculus",
    "forecast": 0.32,
    "resolution_date": null,
    "reasoning": null
}
```

### 5.2 _Dataset_ questions: ≤ 8 forecasts

For every question in `df_dataset` from the [snippet above](How-to-submit-to-ForecastBench#differentiate-between-question-types-and-sources-helpful-snippet), you should provide your model's forecast of the final outcome of the question _at each resolution date_ listed in the `"resolution_dates"` field. There are typically $8$ resolution dates:

$$
\left\lbrace \texttt{forecast due date} + d\ \texttt{days} \mid d \in \left\lbrace 7,30,90,180,365,1095,1825,3650 \right\rbrace \right\rbrace
$$

Note, however, that the number of resolution dates present (and hence the number of forecasts to provide) is determined by the frequency of the series from which the question was generated. If, for example, a series is updated less frequently than weekly, the $7$-day forecast is omitted. 

👀 An example response to a standard dataset question with 8 resolution dates from the [question set due on 2025-03-02](https://raw.githubusercontent.com/forecastingresearch/forecastbench-datasets/refs/heads/main/datasets/question_sets/2025-03-02-llm.json) would look like:
```json
{
    "id": "WFC",
    "source": "yfinance",
    "forecast": 0.53,
    "resolution_date": "2025-03-09",
    "reasoning": null
},
{
    "id": "WFC",
    "source": "yfinance",
    "forecast": 0.55,
    "resolution_date": "2025-04-01",
    "reasoning": null
},
{
    "id": "WFC",
    "source": "yfinance",
    "forecast": 0.57,
    "resolution_date": "2025-05-31",
    "reasoning": null
},
{
    "id": "WFC",
    "source": "yfinance",
    "forecast": 0.59,
    "resolution_date": "2025-08-29",
    "reasoning": null
},
{
    "id": "WFC",
    "source": "yfinance",
    "forecast": 0.63,
    "resolution_date": "2026-03-02",
    "reasoning": null
},
{
    "id": "WFC",
    "source": "yfinance",
    "forecast": 0.67,
    "resolution_date": "2028-03-01",
    "reasoning": null
},
{
    "id": "WFC",
    "source": "yfinance",
    "forecast": 0.7,
    "resolution_date": "2030-03-01",
    "reasoning": null
},
{
    "id": "WFC",
    "source": "yfinance",
    "forecast": 0.72,
    "resolution_date": "2035-02-28",
    "reasoning": null
}
```

# 6. Submit

Upload your forecast set to your GCP bucket folder.

⚠️ To be considered for the leaderboard, your uploaded forecast set must have a timestamp on or before 23:59:59 UTC on the forecast due date.

⚠️ You may submit a maximum of 3 forecast sets per round. If more than 3 forecast sets are submitted, we'll only consider the first 3 in alphabetical order by filename.

⚠️ If you run into a problem uploading to your bucket, or if you're generating forecasts for this round but have not notified us beforehand, please email your forecast file to [forecastbench@forecastingresearch.org](mailto:forecastbench@forecastingresearch.org) before 23:59:59 UTC on the forecast due date. NB: you may need to set all reasoning values to `null` to ensure your forecast file is not too large to be emailed.

⚠️ The value provided for `model` must be accurate on submission and may not be changed after results are posted.

## 6.1 Anonymous submissions

It is possible to submit anonymously to ForecastBench.

To submit anonymously, we will assign you the organization name `Anonymous N` and you would use that for both the `organization` and `model_organizaiton` in the forecast file you submit. Those are the values that map to the `Team` and `Org` columns of the [tournament leaderboard](https://www.forecastbench.org/tournament/). 

By default, anonymous submissions do not appear on the leaderboard. A checkbox must be selected to view their performance.

Anonymous submissions cannot be de-anonymized at a later date. In other words, once the forecast due date has passed, the `organization`, `model_organizaiton`, and `model` fields are fixed. If at a later date you decide to submit forecasts under your organization's name, those forecasts will not be associated with the forecasts that were submitted anonymously.

Finally, the Forecasting Research Institute commits not to publicly name, reference, or otherwise identify any anonymous entity’s organizational identity or personnel in connection with this submission.