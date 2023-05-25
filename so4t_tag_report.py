import json
import requests
import csv
import os


def collector():

    url = os.environ.get('SO_URL')
    key = os.environ.get('SO_KEY')
    token = os.environ.get('SO_TOKEN')

    # SO Business uses a single token for both API v2 and v3
    # SO Enterprise uses a key for API v2 and a token for API v3
    if 'stackoverflowteams.com' in url:
        v2client = V2Client(url, token)
    else:
        v2client = V2Client(url, key)
    v3client = V3Client(url, token)
    
    api_data = {}
    api_data['questions'] = v2client.get_all_questions(
        filter_id='!-(C9p6W5zHzR.xzw(UcCeR(6Z.YqYklUgN-bcu69o-O71EcDlgKKXF)q3H')
    api_data['articles'] = v2client.get_all_articles(filter_id='!.FtrDbhbGaLQMYD--XljcS.1ETL-U')
    api_data['tags'] = v3client.get_all_tags()
    for tag in api_data['tags']:
        tag['smes'] = v3client.get_tag_smes(tag['id'])

    # Uncomment to export data to JSON files
    # for data_name, data in api_data.items():
    #     export_to_json(data_name, data)

    return api_data


class V2Client(object):

    def __init__(self, base_url, api_key):

        if "stackoverflowteams.com" in base_url:
            self.api_url = "https://api.stackoverflowteams.com/2.3"
            self.team_slug = base_url.split("https://stackoverflowteams.com/c/")[1]
            self.token = api_key
            self.api_key = None
        else:
            self.api_url = base_url + "/api/2.3"
            self.team_slug = None
            self.token = None
            self.api_key = api_key


    def get_all_questions(self, filter_id=''):

        endpoint = "/questions"
        endpoint_url = self.api_url + endpoint
    
        return self.get_items(endpoint_url, filter_id)


    def get_all_articles(self, filter_id=''):

        endpoint = "/articles"
        endpoint_url = self.api_url + endpoint

        return self.get_items(endpoint_url, filter_id)


    def get_items(self, endpoint_url, filter_id):
        
        params = {
            'page': 1,
            'pagesize': 100,
        }
        if filter_id:
            params['filter'] = filter_id

        # SO Business uses a token, SO Enterprise uses a key
        if self.token:
            headers = {'X-API-Access-Token': self.token}
            params['team'] = self.team_slug
        else:
            headers = {'X-API-Key': self.api_key}

        items = []
        while True: # Keep performing API calls until all items are received
            print(f"Getting page {params['page']} from {endpoint_url}")
            response = requests.get(endpoint_url, headers=headers, params=params)
            if response.status_code != 200:
                print(f"/{endpoint_url} API call failed with status code: {response.status_code}.")
                print(response.text)
                print(f"Failed request URL and params: {response.request.url}")
                break

            items_data = response.json().get('items')
            items += items_data
            if not response.json().get('has_more'):
                break

            # If the endpoint gets overloaded, it will send a backoff request in the response
            # Failure to backoff will result in a 502 Error
            if response.json().get('backoff'):
                print("Backoff request received from endpoint. Waiting 15 seconds...")
                os.times.sleep(15)
            params['page'] += 1

        return items
    

class V3Client(object):

    def __init__(self, base_url, token):

        self.token = token
        if "stackoverflowteams.com" in base_url:
            self.team_slug = base_url.split("https://stackoverflowteams.com/c/")[1]
            self.api_url = f"https://api.stackoverflowteams.com/v3/teams/{self.team_slug}"
        else:
            self.api_url = base_url + "/api/v3"


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

        get_response = getattr(requests, method, None)
        endpoint_url = self.api_url + endpoint
        headers = {'Authorization': f'Bearer {self.token}'}

        data = []
        while True:
            if method == 'get':
                response = get_response(endpoint_url, headers=headers, params=params)
            else:
                response = get_response(endpoint_url, headers=headers, json=params)

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


def create_tag_report(api_data):

    questions = api_data['questions']
    tags = api_data['tags']
    articles = api_data['articles']

    tag_metrics, tag_users = calculate_tag_metrics(tags, questions, articles)

    # Uncomment to export data to JSON
    # export_to_json('tag_metrics', tag_metrics)
    # export_to_json('tag_users', tag_users)

    export_to_csv('tag_metrics', tag_metrics)

    return tag_metrics


def calculate_tag_metrics(tags, questions, articles):
    
    tag_metrics = {}
    tag_contributors = {}
    tag_users = {}

    for tag in tags:
        tag_name = tag['name']
        tag_metrics[tag_name] = {
            'tag': tag_name,
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
            'answer_count': 0,
            'answer_upvotes': 0,
            'answer_downvotes': 0,
            'answer_comments': 0,
            'article_count': 0,
            'article_upvotes': 0,
            'article_comments': 0
        }
        tag_contributors[tag_name] = {
            'askers': [],
            'answerers': [],
            'article_contributors': [],
            'commenters': [],
            'individual_smes': [],
            'group_smes': []
        }
        tag_users[tag_name] = {}

        # calculate total unique SMEs, including individuals and groups
        for user in tag['smes']['users']:
            tag_contributors[tag_name]['individual_smes'] = add_user_to_list(
                user['id'], tag_contributors[tag_name]['individual_smes'])
        for group in tag['smes']['userGroups']:
            for user in group['users']:
                tag_contributors[tag_name]['group_smes'] = add_user_to_list(
                    user['id'], tag_contributors[tag_name]['group_smes'])
        
        tag_metrics[tag_name]['individual_smes'] = len(
            tag_contributors[tag_name]['individual_smes'])
        tag_metrics[tag_name]['group_smes'] = len(tag_contributors[tag_name]['group_smes'])
        tag_metrics[tag_name]['total_unique_smes'] = len(set(
            tag_contributors[tag_name]['individual_smes'] + tag_contributors[tag_name]['group_smes']
        ))

    # calculate tag metrics for questions
    for question in questions:
        for tag in question['tags']:
            tag_users, tag_contributors, asker_id = validate_tag_user(
                tag_users, tag_contributors, tag, question['owner']
            )
            tag_metrics[tag]['question_count'] += 1
            tag_users[tag][asker_id]['questions'] += 1
            tag_metrics[tag]['total_page_views'] += question['view_count']
            tag_metrics[tag]['question_upvotes'] += question['up_vote_count']
            tag_users[tag][asker_id]['question_upvotes'] += question['up_vote_count']
            tag_metrics[tag]['question_downvotes'] += question['down_vote_count']
            tag_contributors[tag]['askers'] = add_user_to_list(
                asker_id, tag_contributors[tag]['askers']
            )
            if question.get('comments'):
                tag_metrics[tag]['question_comments'] += len(question['comments'])
                for comment in question['comments']:
                    tag_users, tag_contributors, commenter_id = validate_tag_user(
                        tag_users, tag_contributors, tag, comment['owner']
                    )
                    tag_contributors[tag]['commenters'] = add_user_to_list(
                        commenter_id, tag_contributors[tag]['commenters']
                    )
                    tag_users[tag][commenter_id]['comments'] += 1
                    tag_users[tag][commenter_id]['comment_upvotes'] += comment['score']
            

            # calculate tag metrics for answers
            if question.get('answers'):
                for answer in question['answers']:
                    tag_users, tag_contributors, answerer_id = validate_tag_user(
                        tag_users, tag_contributors, tag, answer['owner']
                    )
                    tag_contributors[tag]['answerers'] = add_user_to_list(
                        answerer_id, tag_contributors[tag]['answerers']
                    )
                    if answer['is_accepted']:
                        tag_metrics[tag]['questions_accepted_answer'] += 1
                        tag_users[tag][answerer_id]['answers_accepted'] += 1
                    tag_metrics[tag]['answer_count'] += 1
                    tag_users[tag][answerer_id]['answers'] += 1
                    tag_metrics[tag]['answer_upvotes'] += answer['up_vote_count']
                    tag_users[tag][answerer_id]['answer_upvotes'] += answer['up_vote_count']
                    tag_metrics[tag]['answer_downvotes'] += answer['down_vote_count']

                    if answer.get('comments'):
                        tag_metrics[tag]['answer_comments'] += len(answer['comments'])
                        for comment in answer['comments']:
                            tag_users, tag_contributors, commenter_id = validate_tag_user(
                                tag_users, tag_contributors, tag, comment['owner']
                            )
                            tag_contributors[tag]['commenters'] = add_user_to_list(
                                commenter_id, tag_contributors[tag]['commenters']
                            )
                            tag_users[tag][commenter_id]['comments'] += 1
                            tag_users[tag][commenter_id]['comment_upvotes'] += comment['score']
            else:
                tag_metrics[tag]['questions_no_answers'] += 1
    
    # calculate tag metrics for articles
    for article in articles:
        for tag in article['tags']:
            tag_users, tag_contributors, article_author_id = validate_tag_user(
                tag_users, tag_contributors, tag, article['owner']
            )
            tag_metrics[tag]['total_page_views'] += article['view_count']
            tag_metrics[tag]['article_count'] += 1
            tag_users[tag][article_author_id]['articles'] += 1
            tag_metrics[tag]['article_upvotes'] += article['score']
            tag_users[tag][article_author_id]['article_upvotes'] += article['score']
            tag_metrics[tag]['article_comments'] += article['comment_count']
            tag_contributors[tag]['article_contributors'] = add_user_to_list(
                article_author_id, tag_contributors[tag]['article_contributors']
            )
            tag_metrics[tag]['unique_article_contributors'] = len(
                tag_contributors[tag]['article_contributors'])

            # As of 2023.05.23, Article comments are currently innaccurate due to a bug in the API
            # if article.get('comments'):
            #     for comment in article['comments']:
            #         commenter_id = validate_user_id(comment)
            #         tag_contributors[tag]['commenters'] = add_user_to_list(
            #             commenter_id, tag_contributors[tag]['commenters']
            #         )

    # calculate unique tag contributors across all types of content
    for tag, tag_data in tag_metrics.items():
        tag_data['unique_askers'] = len(tag_contributors[tag]['askers'])
        tag_data['unique_answerers'] = len(tag_contributors[tag]['answerers'])
        tag_data['unique_commenters'] = len(tag_contributors[tag]['commenters'])
        tag_data['unique_article_contributors'] = len(
            tag_contributors[tag]['article_contributors'])
        tag_data['unique_contributors'] = len(set(
            tag_contributors[tag]['askers'] + tag_contributors[tag]['answerers'] +
            tag_contributors[tag]['commenters'] + tag_contributors[tag]['article_contributors']
        ))

    tags_sorted_by_view_count = sorted(
        tag_metrics.items(), key = lambda x: x[1]['total_page_views'], reverse=True)
    
    return tags_sorted_by_view_count, tag_users


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


def validate_tag_user(tag_users, tag_contributors, tag, user):

    try:
        user_id = user['user_id']
    except KeyError:
        user_id = 'unknown'
        user['display_name'] = None
        user['link'] = None
    
    if user_id not in tag_users[tag]:
        tag_users[tag][user_id] = {
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
        if user_id in tag_contributors[tag]['individual_smes']:
            tag_users[tag][user_id]['sme_individual'] = True
        if user_id in tag_contributors[tag]['group_smes']:
            tag_users[tag][user_id]['sme_group'] = True

    return tag_users, tag_contributors, user_id


def export_to_csv(data_name, data):

    file_name = data_name + '.csv'
    csv_header = list(data[0][1].keys())

    with open(file_name, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)
        for tag_data in data:
            writer.writerow(list(tag_data[1].values()))

    print(f'CSV file created: {file_name}')


def export_to_json(data_name, data):
    file_name = data_name + '.json'

    with open(file_name, 'w') as f:
        json.dump(data, f)


if __name__ == '__main__':

    api_data = collector()
    create_tag_report(api_data)
