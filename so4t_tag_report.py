'''
This Python script is offered with no formal support from Stack Overflow. 
If you run into difficulties, reach out to the person who provided you with this script.
Or, open an issue here: https://github.com/jklick-so/so4t_tag_report/issues
'''

# Standard Python libraries
import argparse
import csv
import json
import os
import time
from statistics import median

# Third-party libraries
import requests


def main():

    # Get command-line arguments
    args = get_args()

    # If --no-api is used, skip API calls and use existing JSON data
    if args.no_api:
        api_data = read_json('api_data.json')
    else:
        api_data = data_collector(args)

    # If --days is used, filter API data by date
    if args.days:
        api_data = filter_api_data_by_date(api_data, args.days)
        create_tag_report(api_data, args.days)
    else:
        create_tag_report(api_data)


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

    return parser.parse_args()


def data_collector(args):

    # Import V2Client and V3Client classes to make API calls
    v2client = V2Client(args)
    v3client = V3Client(args)
    
    # Get all questions, articles, tags, and SMEs
    api_data = {}
    api_data['questions'] = get_questions_answers_comments(v2client)
    api_data['articles'] = get_articles(v2client)
    api_data['tags'] = get_tags(v3client)

    # Export API data to JSON file
    export_to_json('api_data', api_data)

    return api_data


def get_questions_answers_comments(v2client):

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

    # API v3 has additional tag data that API v2 does not have
    tags = v3client.get_all_tags()

    # get subject matter experts (SMEs) for each tag
    for tag in tags:
        tag['smes'] = v3client.get_tag_smes(tag['id']) 

    return tags


class V2Client(object):

    def __init__(self, args):

        if not args.url:
            print("Missing required argument. Please provide a URL.")
            print("See --help for more information")
            raise SystemExit
        
        if "stackoverflowteams.com" in args.url:
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
        else:
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

        endpoint = "/filters/create"
        endpoint_url = self.api_url + endpoint

        params = {
            'base': base,
            'unsafe': False
        }

        if filter_attributes:
            # convert list of attributes to semi-colon separated string
            params['include'] = ';'.join(filter_attributes)

        response = self.get_items(endpoint_url, params)
        filter_string = response[0]['filter']
        print(f"Filter created: {filter_string}")

        return filter_string


    def get_all_questions(self, filter_string=''):

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

        endpoint = "/articles"
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
            if response.json().get('backoff'):
                backoff_time = response.json().get('backoff') + 1
                print(f"API backoff request received. Waiting {backoff_time} seconds...")
                time.sleep(backoff_time)

            params['page'] += 1

        return items
    
class V3Client(object):

    def __init__(self, args):

        if not args.url:
            print("Missing required argument. Please provide a URL.")
            print("See --help for more information")
            raise SystemExit

        if not args.token:
            print("Missing required argument. Please provide an API token.")
            print("See --help for more information")
            raise SystemExit
        else:
            self.token = args.token
            self.headers = {'Authorization': f'Bearer {self.token}'}

        if "stackoverflowteams.com" in args.url:
            self.team_slug = args.url.split("https://stackoverflowteams.com/c/")[1]
            self.api_url = f"https://api.stackoverflowteams.com/v3/teams/{self.team_slug}"
        else:
            self.api_url = args.url + "/api/v3"

        self.ssl_verify = self.test_connection()

    
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

    questions = api_data['questions']
    tags = api_data['tags']
    articles = api_data['articles']

    tags, tag_metrics = calculate_tag_metrics(tags, questions, articles)

    export_to_json('tag_data', tags)

    if days:
        export_to_csv(f'tag_metrics_past_{days}_days', tag_metrics)
    else:
        export_to_csv('tag_metrics', tag_metrics)


def calculate_tag_metrics(tags, questions, articles):

    tags = process_tags(tags)
    tags = process_questions(tags, questions)
    tags = process_articles(tags, articles)

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

    tag_metrics = [tag['metrics'] for tag in tags]

    # sort tag_metrics by total page views
    tag_metrics = sorted(tag_metrics, key=lambda k: k['total_page_views'], reverse=True)
    
    return tags, tag_metrics


def process_tags(tags):

    for tag in tags:
        tag['metrics'] = {
            'tag_name': tag['name'],
            'total_page_views': 0,
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


def get_tag_index(tags, tag_name):

    for index, tag in enumerate(tags):
        if tag['name'] == tag_name:
            return index


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
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data


if __name__ == '__main__':

    main()

