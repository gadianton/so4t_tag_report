# Stack Overflow for Teams Tag Report (so4t_tag_report)
An API script for Stack Overflow for Teams that outputs a report (CSV file) of how well each tag is performing. You can see an example of what the output looks like in the Examples directory ([here](https://github.com/jklick-so/so4t_tag_report/blob/main/Examples/tag_metrics.csv)).

All data obtained via the API is handled locally on the device from which the script is run. The script does not transmit data to other parties, such as Stack Overflow.

## Requirements
* A Stack Overflow for Teams instance (Basic, Business, or Enterprise)
* Python 3.x ([download](https://www.python.org/downloads/))
* Operating system: Linux, MacOS, or Windows

## Setup

[Download](https://github.com/jklick-so/so4t_tag_report/archive/refs/heads/main.zip) and unpack the contents of this repository

**Installing Dependencies**

There's only a single depedency: the [Requests](https://pypi.org/project/requests/) library for Python. If you already have it installed, you can skip to API authentication.
* Open a terminal window
* Navigate to the directory where you unpacked the files
* Install the dependencies: `pip3 install -r requirements.txt`

**API Authentication**

For the Basic and Business tiers, you'll need an API token. For Enterprise, you'll need to obtain both an API key and an API token.

* For Basic or Business, instructions for creating a personal access token (PAT) can be found in [this KB article](https://stackoverflow.help/en/articles/4385859-stack-overflow-for-teams-api).
* For Enteprise, documentation for creating the key and token can be found within your instance, at this url: `https://[your_site]/api/docs/authentication`

**Setting Environment Variables**

Now that you have authentication for the API, securely store it within your environment variables. The script leverages the following environment variable names:
* `SO_URL`
* `SO_TOKEN`
* `SO_KEY` (only for Enterprise; Basic/Business can skip this)

Note regarding URLs:
* For Basic and Business, the URL will follow this format: `https://stackoverflowteams.com/c/your-instance-slug`
* For Enterprise, the URL will *usually* follow this format: `https://your-subdomain.stackenterprise.co`

> NOTE: the following instructions are for setting _temporary_ environment variables. After setting the environment variables, leave your terminal window open for the subsequent steps.

**MacOS/Linux**

Open a terminal window and run the following commands:
* `export SO_URL="https://YOUR.INSTANCE.URL"`
* `export SO_TOKEN="YOUR_API_TOKEN"`
* \[Enterprise Only\] `export SO_KEY="YOUR_API_KEY"`

**Windows**

Open a command prompt (cmd.exe) and run the following commands
* `set SO_URL="https://YOUR.INSTANCE.URL"`
* `set SO_TOKEN="YOUR_API_TOKEN"`
* \[Enterprise Only\] `set SO_KEY="YOUR_API_KEY"`

## Usage
Now, it's time to run the script and generate the tag report. 
* In the same terminal window, navigate to the directory where you unpacked the script.
* Run the script: `python3 run so4t_tag_report.py`

The script can take several minutes to run, particularly gathering data from the API. As the script runs, it will continue to update the terminal window with what it's doing.

When the script completes, it will indicate the the CSV has been exported, along with the name of file. You can see an example of what the output looks like [here](https://github.com/jklick-so/so4t_tag_report/blob/main/Examples/tag_metrics.csv).
