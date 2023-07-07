# Stack Overflow for Teams Tag Report (so4t_tag_report)
An API script for Stack Overflow for Teams that creates a report (CSV file) of how well each tag is performing. You can see an example of what the output looks like in the Examples directory ([here](https://github.com/jklick-so/so4t_tag_report/blob/main/Examples/tag_metrics.csv)).

All data obtained via the API is handled locally on the device from which the script is run. The script does not transmit data to other parties, such as Stack Overflow. All of the API calls performed are read only, so there is no risk of editing or adding content on your Stack Overflow for Teams instance.

This script is offered with no formal support from Stack Overflow. If you run into issues using the script, please [open an issue](https://github.com/jklick-so/so4t_tag_report/issues) and/or reach out to the person who provided it to you. You are also welcome to edit the script to suit your needs.

## Requirements
* A Stack Overflow for Teams instance (Basic, Business, or Enterprise)
* Python 3.x ([download](https://www.python.org/downloads/))
* Operating system: Linux, MacOS, or Windows

## Setup

[Download](https://github.com/jklick-so/so4t_tag_report/archive/refs/heads/main.zip) and unpack the contents of this repository

**Installing Dependencies**

* Open a terminal window (or, for Windows, a command prompt)
* Navigate to the directory where you unpacked the files
* Install the dependencies: `pip3 install -r requirements.txt`

**API Authentication**

For the Basic and Business tiers, you'll need an API token. For Enterprise, you'll need to obtain both an API key and an API token.

* For Basic or Business, instructions for creating a personal access token (PAT) can be found in [this KB article](https://stackoverflow.help/en/articles/4385859-stack-overflow-for-teams-api).
* For Enteprise, documentation for creating the key and token can be found within your instance, at this url: `https://[your_site]/api/docs/authentication`

Creating an access token for Enterpise can sometimes be tricky for people who haven't done it before. Here are some (hopefully) straightforward instructions:
* Go to the page where you created your API key. Take note of the "Client ID" associated with your API key.
* Go to the following URL, replacing the base URL, the `client_id`, and base URL of the `redirect_uri` with your own:
`https://YOUR.SO-ENTERPRISE.URL/oauth/dialog?client_id=111&redirect_uri=https://YOUR.SO-ENTERPRISE.URL/oauth/login_success`
* You may be prompted to login to Stack Overflow Enterprise, if you're not already. Either way, you'll be redirected to a page that simply says "Authorizing Application"
* In the URL of that page, you'll find your access token. Example: `https://YOUR.SO-ENTERPRISE.URL/oauth/login_success#access_token=sRsbqFUEk7FW4c9N3zirWQ))`

## Basic Usage
In a terminal window, navigate to the directory where you unpacked the script. 
Run the script using the following format, replacing the URL, token, and/or key with your own:
* For Basic and Business: `python3 so4t_tag_report.py --url "https://stackoverflowteams.com/c/TEAM-NAME" --token "YOUR_TOKEN"`
* For Enterprise: `python3 so4t_tag_report.py --url "https://SUBDOMAIN.stackenterprise.co" --key "YOUR_KEY" --token "YOUR_TOKEN"`

The script can take several minutes to run, particularly as it gathers data via the API. As it runs, it will continue to update the terminal window with the tasks it's performing.

When the script completes, it will indicate the the CSV has been exported, along with the name of file. You can see an example of what the output looks like [here](https://github.com/jklick-so/so4t_tag_report/blob/main/Examples/tag_metrics.csv).

## Advanced Usage
There are two additional arguments you can add to the command line: `--days` and `--no-api`. All arguments (and instructions) can also be found by running the `--help` argument: `python3 so4t_tag_report.py --help`

By default, the CSV report aggregates all historical data for the tags. If you'd like to filter this based on a certain amount of history, the `--days` argument can be used to indicate how many days of history you want to use for the CSV report. If you wanted to pull just the last 90 days worth of data, it would look like this:
`python3 so4t_tag_report.py --url "https://SUBDOMAIN.stackenterprise.co" --key "1oklfRnLqQX49QehDBWzP3Q((" --token "uDtDkCATuydvpj2RzXFOaA))" --days 90`

In conjunction with the `--days` argument, `--no-api` allows you to use leverage preexisting JSON data from an earlier series of API calls (via this script). This is significantly faster than running all the API calls again; in fact, it's nearly instantaneous. If you were looking to generate tag metrics based on a variety of time ranges (via `--days`), using the `--no-api` argument would sigificantly speed up the process. 

Example:
* You generate an initial CSV report via the Basic Usage instructions: `python3 so4t_tag_report.py --url "https://SUBDOMAIN.stackenterprise.co" --key "YOUR_KEY" --token "YOUR_TOKEN"`
* As part of collecting data via the API, an `api_data.json` file is generated and stored locally. For subsequent runs of the script where you're trying to generate the report for different time ranges, you can use the preexisting `api_data.json` data by leveraging the `--no-api` argument.
* To quickly generate a CSV report for the past 30 days: `python3 so4t_tag_report.py --no-api --days 30`
* Then, you generate a report for the past 90 days: `python3 so4t_tag_report.py --no-api --days 90`

Note: when using `--no-api`, the `--url`, `--key`, and `--token` arguments are unecessary. When you'd like to update the JSON data via fresh API calls, simply remove the `no-api` argument and add back the required authentication arguments.

