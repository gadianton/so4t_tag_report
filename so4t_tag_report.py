'''
This Python script is a labor of love and has no formal support from Stack Overflow. 
If you run into difficulties, reach out to the person who provided you with this script.
Or, open an issue here: https://github.com/jklick-so/so4t_tag_report/issues
'''

# Standard Python libraries
import argparse
import csv
import json
import os
import pickle
import re
import time
from statistics import median

# Third-party libraries
import requests
from selenium import webdriver
from bs4 import BeautifulSoup


def main():

    # Get command-line arguments
    args = get_args()

    # If --no-api is used, skip API calls and use existing JSON data
    if args.no_api:
        so4t_data = {}
        try:
            so4t_data['questions'] = read_json('questions.json')
            so4t_data['articles'] = read_json('articles.json')
            so4t_data['tags'] = read_json('tags.json')
            so4t_data['users'] = read_json('users.json')
            so4t_data['webhooks'] = read_json('webhooks.json')
        except FileNotFoundError:
            print('Required JSON data not found.')
            print('Please run the script without the --no-api argument to collect data via API.')
            raise SystemExit
    else:
        so4t_data = data_collector(args)

    # If --days is used, filter API data by date
    if args.days:
        so4t_data = filter_api_data_by_date(so4t_data, args.days)
        create_tag_report(so4t_data, args.days)
    else:
        create_tag_report(so4t_data)


def get_args():

    parser = argparse.ArgumentParser(
        prog='so4t_tag_report.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Uses the Stack Overflow for Teams API to create \
        a CSV report with performance metrics for each tag.',
        epilog = 'Example for Stack Overflow Business: \n'
                'python3 so4t_tag_report.py --url "https://stackoverflowteams.com/c/TEAM-NAME" '
                '--token "YOUR_TOKEN" \n\n'
                'Example for Stack Overflow Enterprise: \n'
                'python3 so4t_tag_report.py --url "https://SUBDOMAIN.stackenterprise.co" '
                '--key "YOUR_KEY" --token "YOUR_TOKEN"\n\n')
    
    parser.add_argument('--url', 
                        type=str,
                        help='Base URL for your Stack Overflow for Teams instance. '
                        'Required if --no-api is not used')
    parser.add_argument('--token',
                        type=str,
                        help='API token for your Stack Overflow for Teams instance. '
                        'Required if --no-api is not used')
    parser.add_argument('--key',
                    type=str,
                    help='API key value. Required if using Enterprise and --no-api is not used')
    
    parser.add_argument('--no-api',
                        action='store_true',
                        help='If API data has already been collected, skip API calls and use '
                        'existing JSON data. This negates the need for --url, --token, or --key.')
    parser.add_argument('--days',
                        type=int,
                        help='Only include metrics for content created within the past X days. '
                        'Default is to include all history')
    parser.add_argument('--scraper',
                        action='store_true',
                        help='Enables web scraping for extra data not available via API. Will '
                        'open a Chrome window and prompt manual login.')
    parser.add_argument('--save-session',
                        action='store_true',
                        help='Saves the authenticated scraping session (cookies) to a file. This '
                        'mitigates the need to log in manually each time the script is run.')

    return parser.parse_args()


def data_collector(args):

    # Only create a web scraping session if the --scraper flag is used
    if args.scraper:
        session_file = 'so4t_session'
        try:
            with open(session_file, 'rb') as f:
                session_data = pickle.load(f)
            scraper = session_data[0]
            scraper.s.cookies = session_data[1]
            if scraper.base_url != args.url or not scraper.test_session():
                print('Previous session is invalid or expired. Creating new session...')
                scraper = WebScraper(args)
            else:
                print('Using previously saved session...')
        except FileNotFoundError:
            print('Previous session not found. Creating new session...')
            scraper = WebScraper(args)
            # If --save-session is used, save the authenticated session to a file
            if args.save_session:
                session_data = [scraper, scraper.s.cookies]
                pickle.dump(session_data, open(session_file, 'wb'))
                print(f"Session saved to file: '{session_file}'")

    # Instantiate V2Client and V3Client classes to make API calls
    v2client = V2Client(args)
    v3client = V3Client(args)
    
    # Get all questions, answers, comments, articles, tags, and SMEs via API
    so4t_data = {}
    so4t_data['questions'] = get_questions_answers_comments(v2client) # also gets answers/comments
    so4t_data['articles'] = get_articles(v2client)
    so4t_data['tags'] = get_tags(v3client) # also gets tag SMEs
    so4t_data['users'] = get_users(v2client)

    # Get additional data via web scraping
    if args.scraper:
        # Get watched tags for users
        so4t_data['users'] = scraper.get_user_watched_tags(so4t_data['users'])
 
        # Get webhooks
        so4t_data['webhooks'] = scraper.get_webhooks(args.url)

        ### DISABLED SCRAPING FUNCTIONS ###
        #     # Get user title and department
        #     so4t_data['users'] = scraper.get_user_title_and_dept(so4t_data['users'])

        #     # Get login histories for users
        #     so4t_data['users'] = scraper.get_user_login_history(so4t_data['users'])
    else:
        so4t_data['webhooks'] = []

    # Export API data to JSON file
    for name, data in so4t_data.items():
        export_to_json(name, data)

    return so4t_data


def get_questions_answers_comments(v2client):
    
    # The API filter used for the /questions endpoint makes it so that the API returns
    # all answers and comments for each question. This is more efficient than making
    # separate API calls for answers and comments.
    # Filter documentation: https://api.stackexchange.com/docs/filters
    if v2client.soe: # Stack Overflow Enterprise requires the generation of a custom filter
        filter_attributes = [
            "answer.body",
            "answer.body_markdown",
            "answer.comment_count",
            "answer.comments",
            "answer.down_vote_count",
            "answer.last_editor",
            "answer.link",
            "answer.share_link",
            "answer.up_vote_count",
            "comment.body",
            "comment.body_markdown",
            "comment.link",
            "question.answers",
            "question.body",
            "question.body_markdown",
            "question.comment_count",
            "question.comments",
            "question.down_vote_count",
            "question.favorite_count",
            "question.last_editor",
            "question.notice",
            "question.share_link",
            "question.up_vote_count"
        ]
        filter_string = v2client.create_filter(filter_attributes)
    else: # Stack Overflow Business or Basic
        filter_string = '!X9DEEiFwy0OeSWoJzb.QMqab2wPSk.X2opZDa2L'
    questions = v2client.get_all_questions(filter_string)

    return questions


def get_articles(v2client):

    if v2client.soe:
        filter_attributes = [
            "article.body",
            "article.body_markdown",
            "article.comment_count",
            "article.comments",
            "article.last_editor",
            "comment.body",
            "comment.body_markdown",
            "comment.link"
        ]
        filter_string = v2client.create_filter(filter_attributes)
    else: # Stack Overflow Business or Basic
        filter_string = '!*Mg4Pjg9LXr9d_(v'

    articles = v2client.get_all_articles(filter_string)

    return articles


def get_tags(v3client):

    # While API v2 is more robust for collecting tag data, it does not return the tag ID field, 
    # which is needed to get the SMEs for each tag. Therefore, API v3 is used to get the tag ID
    tags = v3client.get_all_tags()

    # Get subject matter experts (SMEs) for each tag. This API call is only available in v3.
    # There's no way to get SME configurations in bulk, so this call must be made for each tag, 
    # making it a bit slower to get through. 
    # FUTURE WORK: implementing some form of concurrency would speed this up.
    for tag in tags:
        tag['smes'] = v3client.get_tag_smes(tag['id']) 

    return tags


def get_users(v2client):

    if v2client.soe: # Stack Overflow Enterprise requires the generation of a custom filter
        filter_attributes = [
                "user.about_me",
                "user.answer_count",
                "user.down_vote_count",
                "user.question_count",
                "user.up_vote_count",
                "user.email" # email is only available for Stack Overflow Enterprise
        ]
        filter_string = v2client.create_filter(filter_attributes)
    else: # Stack Overflow Business or Basic
        filter_string = '!6WPIommaBqvsI'

    # Get all users via API
    users = v2client.get_all_users(filter_string)

    # Exclude users with an ID of less than 1 (i.e. Community user and user groups)
    users = [user for user in users if user['user_id'] > 1]

    return users

class WebScraper(object):
    
    def __init__(self, args):
    
        if "stackoverflowteams.com" in args.url: # Stack Overflow Business or Basic
            self.soe = False
        else: # Stack Overflow Enterprise
            self.soe = True
        
        self.base_url = args.url
        self.s = self.create_session() # create a Requests session with authentication cookies
        self.admin = self.validate_admin_permissions() # check if user has admin permissions


    def create_session(self):

        # Configure Chrome driver
        options = webdriver.ChromeOptions()
        options.add_argument("--window-size=500,800")
        options.add_experimental_option("excludeSwitches", ['enable-automation'])
        driver = webdriver.Chrome(options=options)

        # Check if URL is valid
        try:
            response = requests.get(self.base_url)
        except requests.exceptions.SSLError:
            print(f"SSL certificate error when trying to access {self.base_url}.")
            print("Please check your URL and try again.")
            raise SystemExit
        except requests.exceptions.ConnectionError:
            print(f"Connection error when trying to access {self.base_url}.")
            print("Please check your URL and try again.")
            raise SystemExit
        
        if response.status_code != 200:
            print(f"Error when trying to access {self.base_url}.")
            print(f"Status code: {response.status_code}")
            print("Please check your URL and try again.")
            raise SystemExit
        
        # Open a Chrome window and log in to the site
        driver.get(self.base_url)
        while True:
            try:
                # if user card is found, login is complete
                driver.find_element("class name", "s-user-card")
                break
            except:
                time.sleep(1)
        
        # pass authentication cookies from Selenium driver to Requests session
        cookies = driver.get_cookies()
        s = requests.Session()
        for cookie in cookies:
            s.cookies.set(cookie['name'], cookie['value'])
        driver.close()
        driver.quit()
        
        return s
    

    def test_session(self):

        soup = self.get_page_soup(f"{self.base_url}/users")
        if soup.find('div', {'class': 's-user-card'}):
            return True
        else:
            return False


    def validate_admin_permissions(self):

        # The following URLs are only accessible to users with admin permissions
        # If the user does not have admin permissions, the page will return a 404 error
        if self.soe:
            admin_url = self.base_url + '/enterprise/admin-settings'
        else:
            admin_url = self.base_url + '/admin/settings'

        response = self.get_page_response(admin_url)
        if response.status_code != 200:
            print("User does not have admin permissions.")
            return False
        else:
            return True


    def get_user_title_and_dept(self, users):
        # This function goes to the profile page of each user and gets their title and department
        # This data is not available via the API
        # Requires that the title and departement assertions have been configured in the SAML
        # settings; otherwise, the title and department will not be displayed on the profile page

        for user in users:
            if user['user_id'] <= 1: # skip the Community user and user groups
                continue

            print(f"Getting title and department for user ID {user['user_id']}")
            user_url = f"{self.base_url}/users/{user['user_id']}"
            soup = self.get_page_soup(user_url)
            title_dept = soup.find('div', {'class': 'mb8 fc-light fs-title lh-xs'})
            try:
                user['department'] = title_dept.text.split(', ')[-1]
                user['title'] = title_dept.text.split(f", {user['department']}")[0]
            except AttributeError: # if no title/dept returned, `text` method will not work on None
                user['department'] = ''
            except IndexError: # if using old title format
                user['title'] = title_dept.text
                user['department'] = ''
        
        return users
    

    def get_user_watched_tags(self, users):
        # This function goes to the watched tags page of each user and gets their watched tags
        # This data is not available via the API
        # It requires Stack Overflow Enterprise and admin permissions, both of which are checked

        if not self.soe: # check if using Stack Overflow Enterprise
            print('Not able to obtain user watched tags. This is only available on '
                  'Stack Overflow Enterprise.')
            return users
        
        if not self.admin: # check if user has admin permissions
            print('Not able to obtain user watched tags. This requires admin permissions.')
            return users

        for user in users:
            if user['user_id'] <= 1: # skip the Community user and user groups
                continue

            print(f"Getting watched tags for user ID {user['user_id']}")
            watched_tags_url = f"{self.base_url}/users/tag-notifications/{user['user_id']}"
            soup = self.get_page_soup(watched_tags_url)
            try:
                watched_tag_rows = soup.find('table', {'class': '-settings'}).find_all('tr')
                user['watched_tags'] = [self.strip_html(tag.find('td').text) 
                                        for tag in watched_tag_rows]
            except AttributeError: # if user has no watched tags
                print(f"User ID {user['user_id']} does not have a watched tags page")
                user['watched_tags'] = []
                pass

        return users


    def get_user_login_history(self, users):
        # This function goes to the account page of each user and gets their login history and
        # presents it as a list of timestamps
        # This data is not available via the API
        # It requires Stack Overflow Enterprise and admin permissions, both of which are checked

        if not self.soe: # check if using Stack Overflow Enterprise
            print('Not able to obtain user login history. This is only available on '
                  'Stack Overflow Enterprise.')
            return users
        
        if not self.admin: # check if user has admin permissions
            print('Not able to obtain user login history. This requires admin permissions.')
            return users

        for user in users:
            if user['user_id'] <= 1: # skip the Community user and user groups
                continue

            print(f"Getting login history for account ID {user['account_id']}")
            account_url = f"{self.base_url}/accounts/{user['account_id']}"
            soup = self.get_page_soup(account_url)
            try:
                login_history = soup.find(
                    'h2', string=re.compile('Login Histories')).find_next_sibling('table')
            except AttributeError: # if user has no login history
                user['login_history'] = []
                continue
            
            login_timestamps = []
            for row in login_history.find_all('tr'):
                if row.find('th'): # skip the header row
                    continue
                timestamp = row.find('td').find('span')['title']
                # create datetime object from timestamp string
                # timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%SZ')
                login_timestamps.append(timestamp)
            user['login_history'] = login_timestamps

        return users
    

    def get_webhooks(self, base_url):
        # This function gets all webhooks configured for Stack Overflow for Teams instance
        # This data is not available via the API
        # It requires admin permissions, which is checked for
        # The scraped data requires a bit of processing to get it into a usable format, which has
        # been split off into a separate process_webhooks function

        if not self.admin: # check if user has admin permissions
            print('Not able to obtain webhook data. User is not an admin or URL is invalid')
            return []
        
        webhooks = []
        if self.soe: # Stack Overflow Enterprise
            webhooks_url = f"{self.base_url}/enterprise/webhooks"
            page_count = self.get_page_count(webhooks_url + '?page=1&pagesize=50')
            for page in range(1, page_count + 1):
                print(f"Getting webhooks from page {page} of {page_count}")
                page_url = webhooks_url + f'?page={page}&pagesize=50'
                webhooks += self.scrape_webhooks_page(page_url)
            print(f"Found {len(webhooks)} webhooks")

        else: # Stack Overflow Business or Basic
            slack_webhooks_url = f"{self.base_url}/admin/integrations/slack"
            print(f"Getting webhooks from {slack_webhooks_url}")
            webhooks += self.scrape_webhooks_page(slack_webhooks_url)
            print(f"Found {len(webhooks)} Slack webhooks")

            msteams_webhooks_url = f"{self.base_url}/admin/integrations/microsoft-teams"
            print(f"Getting webhooks from {msteams_webhooks_url}")
            webhooks += self.scrape_webhooks_page(msteams_webhooks_url)
            print(f"Found {len(webhooks)} Microsoft Teams webhooks")

        return webhooks
    

    def scrape_webhooks_page(self, page_url):
        # For Stack Overflow Enterprise, the webhook_type is a column in the table
        # For Stack Overflow Business or Basic, the webhook type isn't in the table, so it's
        # inferred from the URL

        response = self.get_page_response(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        webhook_rows = soup.find_all('tr')

        if self.soe: # Stack Overflow Enterprise
            webhooks = self.process_webhooks(webhook_rows)
        else: # Stack Overflow Business or Basic
            # type should be the the last part of the URL
            type = page_url.split('/')[-1]
            webhooks = self.process_webhooks(webhook_rows, webhook_type=type)

        return webhooks


    def process_webhooks(self, webhook_rows, webhook_type=None):

        # A webhook description has three parts: tags, activity type, and channel
        # Example scenarios to be accounted for:
            # All post activity to Private Channel > Private Channel
            # Any aws kubernetes github amazon-web-services (added via synonyms) kube 
                # (added via synonyms) posts to Engineering > Platform Engineering
            # Any admiral python aws amazon-web-services (added via synonyms) questions, 
                # answers to #admiral
            # Any questions, answers to #help-desk
            # Any machine-learning posts to #mits-demo

        activity_types = ['edited questions', 'updated answers', 'accepted answers', 'questions', 
                        'answers', 'comments']
        webhooks = []
        for row in webhook_rows:
            if row.find('th'):
                continue
            columns = row.find_all('td')
            # Description always starts with "Any" unless it's "All post activity to..."
                # Which means all tags and activity types
            # In the description string, the space-delimited words after "Any" are tags
                # unless the notifications trigger for all tags, in which case it skips to activity type
                # some tags have suffixes like "(added via synonyms)"
            # The word "posts" is used to denote all activity types
            # Activity types are comma-delimited; everything else is space-delimited
            # The words after "to" are the channel; also, surrounded by <b></b> tags

            if self.soe: # For Stack Overflow Enterprise
                webhook_type = self.strip_html(columns[0].text)
                description = self.strip_html(columns[2].text).replace(
                    '(added via synonyms) ', '').replace(',', '')
                creator = columns[3].text
                creation_date = columns[4].text
            else: # For Stack Overflow Business or Basic
                description = self.strip_html(columns[0].text).replace(
                    '(added via synonyms) ', '').replace(',', '')
                creator = columns[1].text
                creation_date = columns[2].text
        
            if description.startswith('All post activity to'):
                tags = ['all']
                activities = activity_types
                channel = description.split('All post activity to ')[1]
            elif description.startswith('Any'):
                description = description.split('Any ')[1] # strip "Any"
                channel = description.split(' to ')[1]
                if 'posts to' in description: # all activity types
                    activities = activity_types
                    tags = description.split(' posts to ')[0].split(' ')
                else: 
                    # Activity types are specified, but tags may or may not be
                    # Of the remaining words, find which are tags and activity types
                    # Activity types are comma-delimited
                    # Tags are space-delimited
                    # Tags are always first
                    # Tags are always followed by activity types
                    description = description.split(' to ')[0] # strip off channel
                    activities = []
                    for activity_type in activity_types:
                        if activity_type in description:
                            activities.append(activity_type)
                            description = description.replace(activity_type, '').strip()
                    if description:
                        tags = description.split(' ')
                    else:
                        tags = ['all']
            else: # likely a webhook that is disabled
                # If a webhook is disabled, it will usually start with the text:
                # "Notification failed, please re-authorize it."
                print(f"Unable to process webhook description: '{description}'")
                continue

            if channel == 'self':
                # For Microsoft Teams' webhooks, when a user selects private notifications,
                # the channel is reported as "self", which isn't very informative. To improve on 
                # that, append "self" with the user's name, who is the creator of the webhook.
                channel = f"{channel} ({creator})"

            webhook = {
                'type': webhook_type,
                'channel': channel,
                'tags': tags,
                'activities': activities,
                'creation_date': creation_date
            }
            webhooks.append(webhook)

        return webhooks

        
    def get_page_response(self, url):
        # Uses the Requests session to get page response

        response = self.s.get(url)
        if not response.status_code == 200:
            print(f'Error getting page {url}')
            print(f'Response code: {response.status_code}')
        
        return response
    

    def get_page_soup(self, url):
        # Uses the Requests session to get page response and returns a BeautifulSoup object

        response = self.get_page_response(url)
        try:
            return BeautifulSoup(response.text, 'html.parser')
        except AttributeError:
            return None
        

    def get_page_count(self, url):
        # Returns the number of pages that need to be scraped

        response = self.get_page_response(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        pagination = soup.find_all('a', {'class': 's-pagination--item js-pagination-item'})
        try:
            page_count = int(pagination[-2].text)
        except IndexError: # only one page
            page_count = 1

        return page_count


    def strip_html(self, text):
        # Remove HTML tags and newlines from text
        # There are various scenarios where these characters are present in the text when scraped
        return re.sub('<[^<]+?>', '', text).replace('\n', '').replace('\r', '').strip()
        

class V2Client(object):

    def __init__(self, args):

        if not args.url: # check if URL is provided; if not, exit
            print("Missing required argument. Please provide a URL.")
            print("See --help for more information")
            raise SystemExit
        
        # Establish the class variables based on which product is being used
        if "stackoverflowteams.com" in args.url: # Stack Overflow Business or Basic
            self.soe = False
            self.api_url = "https://api.stackoverflowteams.com/2.3"
            self.team_slug = args.url.split("https://stackoverflowteams.com/c/")[1]
            self.token = args.token
            self.api_key = None
            self.headers = {'X-API-Access-Token': self.token}
            if not self.token:
                print("Missing required argument. Please provide an API token.")
                print("See --help for more information")
                raise SystemExit
        else: # Stack Overflow Enterprise
            self.soe = True
            self.api_url = args.url + "/api/2.3"
            self.team_slug = None
            self.token = None
            self.api_key = args.key
            self.headers = {'X-API-Key': self.api_key}
            if not self.api_key:
                print("Missing required argument. Please provide an API key.")
                print("See --help for more information")
                raise SystemExit

        # Test the API connection and set the SSL verification variable
        self.ssl_verify = self.test_connection()


    def test_connection(self):

        url = self.api_url + "/tags"
        ssl_verify = True

        params = {}
        if self.token:
            headers = {'X-API-Access-Token': self.token}
            params['team'] = self.team_slug
        else:
            headers = {'X-API-Key': self.api_key}

        print("Testing API 2.3 connection...")
        try:
            response = requests.get(url, params=params, headers=headers)
        except requests.exceptions.SSLError:
            print("SSL error. Trying again without SSL verification...")
            response = requests.get(url, params=params, headers=headers, verify=False)
            ssl_verify = False
        
        if response.status_code == 200:
            print("API connection successful")
            return ssl_verify
        else:
            print("Unable to connect to API. Please check your URL and API key/token.")
            print(response.text)
            raise SystemExit
        

    def create_filter(self, filter_attributes='', base='default'):
        # filter_attributes should be a list variable containing strings of the attributes
        # base can be 'default', 'withbody', 'none', or 'total'

        # Filter documentation: https://api.stackexchange.com/docs/filters
        # Documentation for API endpoint: https://api.stackexchange.com/docs/create-filter
        endpoint = "/filters/create"
        endpoint_url = self.api_url + endpoint

        params = {
            'base': base,
            'unsafe': False
        }

        if filter_attributes:
            # The API endpoint requires a semi-colon separated string of attributes
            # This converts the list of attributes into a string
            params['include'] = ';'.join(filter_attributes)

        response = self.get_items(endpoint_url, params)
        filter_string = response[0]['filter']
        print(f"Filter created: {filter_string}")

        return filter_string


    def get_all_questions(self, filter_string=''):

        # API endpoint documentation: https://api.stackexchange.com/docs/questions
        endpoint = "/questions"
        endpoint_url = self.api_url + endpoint

        params = {
            'page': 1,
            'pagesize': 100,
        }
        if filter_string:
            params['filter'] = filter_string
    
        return self.get_items(endpoint_url, params)


    def get_all_articles(self, filter_string=''):

        # API endpoint documentation: https://api.stackexchange.com/docs/articles
        endpoint = "/articles"
        endpoint_url = self.api_url + endpoint

        params = {
            'page': 1,
            'pagesize': 100,
        }
        if filter_string:
            params['filter'] = filter_string

        return self.get_items(endpoint_url, params)
    

    def get_all_users(self, filter_string=''):
        
        # API endpoint documentation: https://api.stackexchange.com/docs/users
        endpoint = "/users"
        endpoint_url = self.api_url + endpoint

        params = {
            'page': 1,
            'pagesize': 100,
        }
        if filter_string:
            params['filter'] = filter_string

        return self.get_items(endpoint_url, params)


    def get_items(self, endpoint_url, params):
        
        # SO Business and Basic require a team slug parameter
        if not self.soe:
            params['team'] = self.team_slug

        items = []
        while True: # Keep performing API calls until all items are received
            if params.get('page'):
                print(f"Getting page {params['page']} from {endpoint_url}")
            else:
                print(f"Getting data from {endpoint_url}")
            response = requests.get(endpoint_url, headers=self.headers, params=params, 
                                    verify=self.ssl_verify)
            
            if response.status_code != 200:
                # Many API call failures result in an HTTP 400 status code (Bad Request)
                # To understand the reason for the 400 error, specific API error codes can be 
                # found here: https://api.stackoverflowteams.com/docs/error-handling
                print(f"/{endpoint_url} API call failed with status code: {response.status_code}.")
                print(response.text)
                print(f"Failed request URL and params: {response.request.url}")
                break

            items += response.json().get('items')
            if not response.json().get('has_more'):
                break

            # If the endpoint gets overloaded, it will send a backoff request in the response
            # Failure to backoff will result in a 502 error (throttle_violation)
            # Rate limiting documentation: https://api.stackexchange.com/docs/throttle
            if response.json().get('backoff'):
                backoff_time = response.json().get('backoff') + 1
                print(f"API backoff request received. Waiting {backoff_time} seconds...")
                time.sleep(backoff_time)

            params['page'] += 1

        return items
    

class V3Client(object):

    def __init__(self, args):

        if not args.url: # check if URL is provided; if not, exit
            print("Missing required argument. Please provide a URL.")
            print("See --help for more information")
            raise SystemExit

        if not args.token: # check if API token is provided; if not, exit
            print("Missing required argument. Please provide an API token.")
            print("See --help for more information")
            raise SystemExit
        else:
            self.token = args.token
            self.headers = {'Authorization': f'Bearer {self.token}'}

        if "stackoverflowteams.com" in args.url: # Stack Overflow Business or Basic
            self.team_slug = args.url.split("https://stackoverflowteams.com/c/")[1]
            self.api_url = f"https://api.stackoverflowteams.com/v3/teams/{self.team_slug}"
        else: # Stack Overflow Enterprise
            self.api_url = args.url + "/api/v3"

        self.ssl_verify = self.test_connection() # test the API connection

    
    def test_connection(self):

        endpoint = "/tags"
        endpoint_url = self.api_url + endpoint
        ssl_verify = True

        print("Testing API v3 connection...")
        try:
            response = requests.get(endpoint_url, headers=self.headers)
        except requests.exceptions.SSLError:
            print("SSL error. Trying again without SSL verification...")
            response = requests.get(endpoint_url, headers=self.headers, verify=False)
            ssl_verify = False
        
        if response.status_code == 200:
            print("API connection successful")
            return ssl_verify
        else:
            print("Unable to connect to API. Please check your URL and API token.")
            print(response.text)
            raise SystemExit


    def get_all_tags(self):

        method = "get"
        endpoint = "/tags"
        params = {
            'page': 1,
            'pagesize': 100,
        }
        tags = self.send_api_call(method, endpoint, params)

        return tags


    def get_tag_smes(self, tag_id):

        method = "get"
        endpoint = f"/tags/{tag_id}/subject-matter-experts"
        smes = self.send_api_call(method, endpoint)

        return smes


    def send_api_call(self, method, endpoint, params={}):

        get_response = getattr(requests, method, None) # get the method from the requests library
        endpoint_url = self.api_url + endpoint

        data = []
        while True:
            if method == 'get':
                response = get_response(endpoint_url, headers=self.headers, params=params, 
                                        verify=self.ssl_verify)
            else:
                response = get_response(endpoint_url, headers=self.headers, json=params, 
                                        verify=self.ssl_verify)

            # check for rate limiting thresholds
            # print(response.headers) 
            if response.status_code not in [200, 201, 204]:
                print(f"API call to {endpoint_url} failed with status code {response.status_code}")
                print(response.text)
                raise SystemExit
                        
            try:
                json_data = response.json()
            except json.decoder.JSONDecodeError: # some API calls do not return JSON data
                print(f"API request successfully sent to {endpoint_url}")
                return

            if type(params) == dict and params.get('page'): # check request for pagination
                print(f"Received page {params['page']} from {endpoint_url}")
                data += json_data['items']
                if params['page'] == json_data['totalPages']:
                    break
                params['page'] += 1
            else:
                print(f"API request successfully sent to {endpoint_url}")
                data = json_data
                break

        return data


def filter_api_data_by_date(api_data, days):

    today = int(time.time())
    start_date = today - (days * 24 * 60 * 60)  # convert days to seconds

    # Filter questions and articles by creation date
    questions = [question for question in api_data['questions'] 
                 if question['creation_date'] > start_date]
    api_data['questions'] = questions

    articles = [article for article in api_data['articles']
                if article['creation_date'] > start_date]
    api_data['articles'] = articles

    # Uncomment to export filtered data to JSON
    # export_to_json('filtered_api_data', api_data)

    return api_data


def create_tag_report(api_data, days=None):

    api_data['tags'] = process_api_data(api_data)
    export_to_json('tag_data', api_data['tags'])

    tag_metrics = [tag['metrics'] for tag in api_data['tags']]
    tag_metrics = sorted(tag_metrics, key=lambda k: k['total_page_views'], reverse=True)

    if days:
        export_to_csv(f'tag_metrics_past_{days}_days', tag_metrics)
    else:
        export_to_csv('tag_metrics', tag_metrics)


def process_api_data(api_data):

    tags = api_data['tags']

    tags = process_tags(tags)
    tags = process_questions(tags, api_data['questions'])
    tags = process_articles(tags, api_data['articles'])
    tags = process_users(tags, api_data['users'])

    if api_data['webhooks']:
        tags = process_webhooks(tags, api_data['webhooks'])

    # tally up miscellaneous metrics for each tag
    for tag in tags:
        tag['metrics']['unique_askers'] = len(tag['contributors']['askers'])
        tag['metrics']['unique_answerers'] = len(tag['contributors']['answerers'])
        tag['metrics']['unique_commenters'] = len(tag['contributors']['commenters'])
        tag['metrics']['unique_article_contributors'] = len(
            tag['contributors']['article_contributors'])
        tag['metrics']['unique_contributors'] = len(set(
            tag['contributors']['askers'] + 
            tag['contributors']['answerers'] +
            tag['contributors']['commenters'] + 
            tag['contributors']['article_contributors']))
        
        try:
            tag['metrics']['median_answer_time_hours'] = round(median(tag['answer_times']),2)
        except ValueError: # if there are no answers for a tag
            pass
    
    return tags


def process_tags(tags):

    for tag in tags:
        tag['metrics'] = {
            'tag_name': tag['name'],
            'total_page_views': 0,
            'webhooks': 0,
            'tag_watchers': 0,
            'individual_smes': 0,
            'group_smes': 0,
            'total_unique_smes': 0,
            'unique_askers': 0,
            'unique_answerers': 0,
            'unique_commenters': 0,
            'unique_contributors': 0,
            'unique_article_contributors': 0,
            'question_count': 0,
            'question_upvotes': 0,
            'question_downvotes': 0,
            'question_comments': 0,
            'questions_no_answers': 0,
            'questions_accepted_answer': 0,
            'questions_self_answered': 0,
            'answer_count': 0,
            'sme_answers': 0,
            'answer_upvotes': 0,
            'answer_downvotes': 0,
            'answer_comments': 0,
            'median_answer_time_hours': 0,
            'article_count': 0,
            'article_upvotes': 0,
            'article_comments': 0,
        }
        tag['contributors'] = {
            'askers': [],
            'answerers': [],
            'article_contributors': [],
            'commenters': [],
            'individual_smes': [],
            'group_smes': []
        }
        tag['users'] = {}
        tag['answer_times'] = []

        # calculate total unique SMEs, including individuals and groups
        for user in tag['smes']['users']:
            tag['contributors']['individual_smes'] = add_user_to_list(
                user['id'], tag['contributors']['individual_smes'])
        for group in tag['smes']['userGroups']:
            for user in group['users']:
                tag['contributors']['group_smes'] = add_user_to_list(
                    user['id'], tag['contributors']['group_smes'])
        
        tag['metrics']['individual_smes'] = len(
            tag['contributors']['individual_smes'])
        tag['metrics']['group_smes'] = len(tag['contributors']['group_smes'])
        tag['metrics']['total_unique_smes'] = len(set(
            tag['contributors']['individual_smes'] + tag['contributors']['group_smes']))
        
    return tags


def process_questions(tags, questions):

    for question in questions:
        for tag in question['tags']:
            tag_index = get_tag_index(tags, tag)
            tag_data = tags[tag_index]
            tag_data, asker_id = validate_tag_user(tag_data, question['owner'])
            
            tag_data['contributors']['askers'] = add_user_to_list(
                asker_id, tag_data['contributors']['askers'])

            tag_data['users'][asker_id]['question_upvotes'] += question['up_vote_count']
            tag_data['users'][asker_id]['questions'] += 1

            tag_data['metrics']['question_count'] += 1
            tag_data['metrics']['total_page_views'] += question['view_count']
            tag_data['metrics']['question_upvotes'] += question['up_vote_count']
            tag_data['metrics']['question_downvotes'] += question['down_vote_count']

            if question.get('comments'):
                tag_data['metrics']['question_comments'] += len(question['comments'])
                for comment in question['comments']:
                    tag_data, commenter_id = validate_tag_user(tag_data, comment['owner'])
                    tag_data['contributors']['commenters'] = add_user_to_list(
                        commenter_id, tag_data['contributors']['commenters'])
                    
                    tag_data['users'][commenter_id]['comments'] += 1
                    tag_data['users'][commenter_id]['comment_upvotes'] += comment['score']
            
            # calculate tag metrics for answers
            if question.get('answers'):
                tag_data = process_answers(tag_data, question['answers'], question)
            else:
                tag_data['metrics']['questions_no_answers'] += 1

            tags[tag_index] = tag_data

    return tags

        
def process_answers(tag_data, answers, question):

    answer_times = []
    for answer in answers:
        tag_data, answerer_id = validate_tag_user(
            tag_data, answer['owner'])
        tag_data['contributors']['answerers'] = add_user_to_list(
            answerer_id, tag_data['contributors']['answerers'])
        if answer['is_accepted']:
            tag_data['metrics']['questions_accepted_answer'] += 1
            tag_data['users'][answerer_id]['answers_accepted'] += 1
        tag_data['metrics']['answer_count'] += 1
        tag_data['users'][answerer_id]['answers'] += 1
        tag_data['metrics']['answer_upvotes'] += answer['up_vote_count']
        tag_data['users'][answerer_id]['answer_upvotes'] += answer['up_vote_count']
        tag_data['metrics']['answer_downvotes'] += answer['down_vote_count']

        # Calculate number of answers from SMEs
        if (answerer_id in tag_data['contributors']['group_smes'] 
            or answerer_id in tag_data['contributors']['individual_smes']):
            tag_data['metrics']['sme_answers'] += 1

        if answer.get('comments'):
            tag_data['metrics']['answer_comments'] += len(answer['comments'])
            for comment in answer['comments']:
                tag_data, commenter_id = validate_tag_user(
                    tag_data, comment['owner']
                )
                tag_data['contributors']['commenters'] = add_user_to_list(
                    commenter_id, tag_data['contributors']['commenters']
                )
                tag_data['users'][commenter_id]['comments'] += 1
                tag_data['users'][commenter_id]['comment_upvotes'] += comment['score']

        answer_times.append(answer['creation_date'] - question['creation_date'])

    # Use the fastest answer time as the answer time for the question
    if min(answer_times) > 0:
        answer_time_in_hours = min(answer_times)/60/60
        tag_data['answer_times'].append(answer_time_in_hours)
    else: # zero answer time means the answer was posted at same time as question
        tag_data['metrics']['questions_self_answered'] += 1

    return tag_data


def process_articles(tags, articles):

    for article in articles:
        for tag in article['tags']:
            tag_index = get_tag_index(tags, tag)
            tag_data = tags[tag_index]
            tag_data, article_author_id = validate_tag_user(tag_data, article['owner'])
            tag_data['metrics']['total_page_views'] += article['view_count']
            tag_data['metrics']['article_count'] += 1
            tag_data['users'][article_author_id]['articles'] += 1
            tag_data['metrics']['article_upvotes'] += article['score']
            tag_data['users'][article_author_id]['article_upvotes'] += article['score']
            tag_data['metrics']['article_comments'] += article['comment_count']
            tag_data['contributors']['article_contributors'] = add_user_to_list(
                article_author_id, tag_data['contributors']['article_contributors']
            )
            tag_data['metrics']['unique_article_contributors'] = len(
                tag_data['contributors']['article_contributors'])

            # As of 2023.05.23, Article comments are currently innaccurate due to a bug in the API
            # if article.get('comments'):
            #     for comment in article['comments']:
            #         commenter_id = validate_user_id(comment)
            #         tag_contributors[tag]['commenters'] = add_user_to_list(
            #             commenter_id, tag_contributors[tag]['commenters']
            #         )
        
            tags[tag_index] = tag_data

    return tags


def process_users(tags, users):

    if users[0].get('watched_tags'): # if this field exists, the data was collected
        for user in users:
            for tag in user['watched_tags']:
                tag_index = get_tag_index(tags, tag)
                try:
                    tags[tag_index]['metrics']['tag_watchers'] += 1
                except TypeError: # get_tag_index returned None
                    print(f"Watched tag [{tag}] no longer exists for user ID {user['user_id']}")
                    pass
    else: # if this field does not exist, the data was not collected; therefore, remove the metric
        for tag in tags:
            del tag['metrics']['tag_watchers']

    # this is where the user title and department would be added to the report
    # this is also where the user login history would be added to the report

    return tags


def process_webhooks(tags, webhooks):

    if webhooks == None: # if no webhooks were collected, remove the metric from the report
        for tag in tags:
            del tag['metrics']['webhooks']

        return tags
    
    # Search for tags in webhook descriptions and add webhook count to tag metrics
    for webhook in webhooks:
        for tag_name in webhook['tags']:
            tag_index = get_tag_index(tags, tag_name)
            try:
                tags[tag_index]['metrics']['webhooks'] += 1
            except TypeError: # get_tag_index returned None
                pass

    return tags


def get_tag_index(tags, tag_name):

    for index, tag in enumerate(tags):
        if tag['name'] == tag_name:
            return index
    
    return None # if tag is not found


def add_user_to_list(user_id, user_list):
    """Checks to see if a user_id already exists is in a list. If not, it adds the new user_id to 
    the list.

    Args:
        user_id (int): the unique user ID of a particular user in Stack Overflow
        user_list (list): current user list

    Returns:
        user_list (list): updated user list
    """
    if user_id not in user_list:
        user_list.append(user_id)
    return user_list


def validate_tag_user(tag, user):

    try:
        user_id = user['user_id']
    except KeyError:
        user_id = 'unknown'
        user['display_name'] = None
        user['link'] = None
    
    if user_id not in tag['users']:
        tag['users'][user_id] = {
            'id': user_id,
            'name': user['display_name'],
            'profile_url': user['link'],
            'questions': 0,
            'question_upvotes': 0,
            'answers': 0,
            'answer_upvotes': 0,
            'answers_accepted': 0,
            'articles': 0,
            'article_upvotes': 0,
            'comments': 0,
            'comment_upvotes': 0,
            'sme_individual': False,
            'sme_group': False
        }
        if user_id in tag['contributors']['individual_smes']:
            tag['users'][user_id]['sme_individual'] = True
        if user_id in tag['contributors']['group_smes']:
            tag['users'][user_id]['sme_group'] = True

    return tag, user_id


def export_to_csv(data_name, data):

    date = time.strftime("%Y-%m-%d")
    file_name = f"{date}_{data_name}.csv"

    csv_header = [header.replace('_', ' ').title() for header in list(data[0].keys())]
    with open(file_name, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)
        for tag_data in data:
            writer.writerow(list(tag_data.values()))
        
    print(f'CSV file created: {file_name}')


def export_to_json(data_name, data):
    
    file_name = data_name + '.json'
    directory = 'data'

    if not os.path.exists(directory):
        os.makedirs(directory)
    file_path = os.path.join(directory, file_name)

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

    print(f'JSON file created: {file_name}')


def read_json(file_name):
    
    directory = 'data'
    file_path = os.path.join(directory, file_name)
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        raise FileNotFoundError
    
    return data


if __name__ == '__main__':

    main()

