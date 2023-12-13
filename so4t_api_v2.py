# Standard Python libraries
import time

# Third-party libraries
import requests


class V2Client(object):

    def __init__(self, url, token, key):

        if not url: # check if URL is provided; if not, exit
            print("Missing required argument. Please provide a URL.")
            print("See --help for more information")
            raise SystemExit
        
        # Establish the class variables based on which product is being used
        if "stackoverflowteams.com" in url: # Stack Overflow Business or Basic
            self.soe = False
            self.api_url = "https://api.stackoverflowteams.com/2.3"
            self.team_slug = url.split("https://stackoverflowteams.com/c/")[1]
            self.token = token
            self.api_key = None
            self.headers = {'X-API-Access-Token': self.token}
            if not self.token:
                print("Missing required argument. Please provide an API token.")
                print("See --help for more information")
                raise SystemExit
        else: # Stack Overflow Enterprise
            self.soe = True
            self.api_url = url + "/api/2.3"
            self.team_slug = None
            self.token = None
            self.api_key = key
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
  