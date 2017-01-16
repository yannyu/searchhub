import json
import requests
from collections import OrderedDict
from dictdiffer import diff
from server.backends import Backend, Document
from server.backends.github_helper import create_github_datasource_configs
from server.backends.jira_helper import create_jira_datasource_config
from server.backends.mailbox_helper import create_mailinglist_datasource_configs
from server.backends.twitter_helper import create_twitter_datasource_configs
from server.backends.website_helper import create_website_datasource_configs
from server.backends.wiki_helper import create_wiki_datasource_configs
from server.backends.stack_helper import create_stack_datasource_configs
from urlparse import urljoin

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.tools import argparser
import requests

import os
import argparse
import json
import time
import sys
import urllib2

from server import app
import random

class FusionSession(requests.Session):
  """
  Wrapper around requests.Session that manages a cookie-based session
  """

  def __init__(self, proxy_url, username, password, lazy=False):
    super(FusionSession, self).__init__()
    self.__base_url = proxy_url
    self.proxy_url = proxy_url
    print("Using: {0}".format(self.proxy_url))
    self.username = username
    self.password = password
    if not lazy:
      self._authenticate()

  def _authenticate(self):
    headers = {"Content-type": "application/json"}
    data = {'username': self.username, 'password': self.password}
    resp = self.post("session", data=json.dumps(data), headers=headers)
    if resp.status_code == 201:
      pass
    else:
      raise Exception("failed to authenticate, check credentials")

  def request(self, method, url, **kwargs):
    full_url = urljoin(self.__base_url, url)

    resp = super(FusionSession, self).request(method, full_url, **kwargs)
    if resp.status_code == 401:
      if url == "/session":
        return resp
      else:
        print("session expired, re-authenticating")
        self._authenticate()
        return super(FusionSession, self).request(method, full_url, **kwargs)
    else:
      return resp

# The Backend is primarily used by the bootstrap
class FusionBackend(Backend):
  def __init__(self):
    if app.config.get("FUSION_ADMIN_USERNAME"):
      self.admin_session = FusionSession(
        self.get_random_fusion_url(),
        app.config.get("FUSION_ADMIN_USERNAME"),
        app.config.get("FUSION_ADMIN_PASSWORD")
      )

    if app.config.get("FUSION_APP_USER"):
      self.app_session = FusionSession(
        self.get_random_fusion_url(),
        app.config.get("FUSION_APP_USER"),
        app.config.get("FUSION_APP_PASSWORD"),
        lazy=True
      )

def get_videos(id_string, youtube):
  video_details = []
  video_information = youtube.videos().list(
    id= id_string,
    part="snippet, id"
  ).execute()
  for video in video_information["items"]:
    video_details.append({
      "publishedOnDate":video["snippet"]["publishedAt"],
      "datasource_label":"youtube_parser",
      "project_label":"youtube",
      "description":video["snippet"]["description"].encode('utf-8'),
      "content":video["snippet"]["description"].encode('utf-8'),
      "title":video["snippet"]["title"].encode('utf-8'),
      "url":("https://www.youtube.com/watch?v=" + video["id"]).encode('utf-8'),
      "_lw_data_source_s":"website-lucidworks-youtube-lucidworks"
    })
  return video_details

def get_id_string(search_response, youtube):
  id_vals = [d["id"] for d in search_response]
  id_string = ""
  for id_val in id_vals:
    if id_val["kind"] == "youtube#video":
      id_string += id_val["videoId"]+ ","
  return id_string

def get_all_ids(final_video_details, search_response, youtube):
  id_string = get_id_string(search_response["items"], youtube)
  video_details = get_videos(id_string, youtube)
  final_video_details += video_details
  nextPageToken = search_response.get("nextPageToken", [])
  if nextPageToken == []:
    return final_video_details
  else:
    print ("Getting the next page of results!")
    search_response = youtube.search().list(
      channelId="UCPItOdfUk_tjlvqggkY-JsA",
      part="id",
      maxResults=25,
      pageToken=nextPageToken
    ).execute()
    return get_all_ids(final_video_details, search_response, youtube)

  def run_youtube(self):
    DEVELOPER_KEY = app.config.get("DEVELOPER_KEY")
    YOUTUBE_API_SERVICE_NAME = app.config.get("YOUTUBE_API_SERVICE_NAME")
    YOUTUBE_API_VERSION = app.config.get("YOUTUBE_API_VERSION")

DEVELOPER_KEY = "AIzaSyDhPDWg8ghMoJHordyypdIRQHmQEoDsxso"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                developerKey=DEVELOPER_KEY)

    print ("finished making youtube")
search_response = youtube.search().list(
  channelId="UCPItOdfUk_tjlvqggkY-JsA",
  part="id",
  maxResults=25,
).execute()
    print("finished getting search_response")
final_video_details = []
final_list = self.get_all_ids(final_video_details, search_response, youtube)
    print(len(final_list))
json_vids = json.dumps(final_list)
headers = {'content-type': 'application/json'}
    print("Trying to access solr")
r = requests.post("http://localhost:8983/solr/lucidfind/update/json?commit=true", data = json_vids, headers=headers)
r.raise_for_status()
    print("Successfully sent data to solr!")

  def toggle_system_metrics(self, enabled=True):
    print "Setting System Metrics indexing to {0}".format(enabled)
    resp = self.admin_session.put("apollo/configurations/com.lucidworks.apollo.metrics.enabled", data=json.dumps(enabled))
    if resp.status_code != 204:
      print "Unable to set system metrics collection to {0}".format(enabled)
      print resp


  def set_log_level(self, log_level="WARN"):
    print "Setting Log Level to {0}".format(log_level)
    resp = self.admin_session.post("apollo/configurations/com.lucidworks.apollo.log.level", data=json.dumps(log_level))
    if resp.status_code != 204:
      print "Unable to set log_level collection to {0}".format(log_level)
      print resp

  def add_field(self, collection_name, name, type="string", required=False, multivalued=False, indexed=True,
                stored=True, defaultVal=None, copyDests=None):
    data = {
      "name": name,
      "type": type,
      "required": required,
      "multiValued": multivalued,
      "indexed": indexed,
      "stored": stored,
      "default": defaultVal
    }
    if copyDests:
      data["copyDests"] = copyDests
    resp = self.admin_session.post("apollo/collections/{0}/schema/fields".format(collection_name),
                                   data=json.dumps(data))

  def add_field_type(self, collection_name, add_field_json):
    #http://localhost:8983/solr/gettingstarted/schema
    # Need to GET first here and then

    resp = self.admin_session.get("apollo/solr/{0}/fieldtypes/{1}".format(collection_name, add_field_json["name"]))
    if resp.status_code == 200:
      print "Doing a replace on field type {}".format(add_field_json["name"])
      data = {"replace-field-type": add_field_json}
      resp = self.admin_session.post("apollo/solr/{0}/schema".format(collection_name),
                                     data=json.dumps(data))
      if resp.status_code != 200:
        print "Unable to create Field Type: {0}".format(resp.text)
        return False
    else:
      print "Adding field type {}".format(add_field_json["name"])
      data = {"add-field-type": add_field_json}
      resp = self.admin_session.post("apollo/solr/{0}/schema".format(collection_name),
                                     data=json.dumps(data))
      if resp.status_code != 200:
        print "Unable to create Field Type: {0}".format(resp.text)
        return False
    return True

  def set_property(self, collection_name, data):
    set = {"set-property": data}
    resp = self.admin_session.post("apollo/solr/{0}/config".format(collection_name),
                                   data=json.dumps(set))
    errors = self.check_bulk_api_for_errors(resp.json())
    if resp.status_code != 200 or errors:
      print "Couldn't create config, trying replace {0}".format(data)
    else:
      print "Set Property"
    return True

  def unset_property(self, collection_name, data):
    set = {"unset-property": data}
    resp = self.admin_session.post("apollo/solr/{0}/config".format(collection_name),
                                   data=json.dumps(set))
    errors = self.check_bulk_api_for_errors(resp.json())
    if resp.status_code != 200 or errors:
      print "Couldn't create config, trying replace {0}".format(data)
    else:
      print "UnSet Property"
    return True

  def add_search_component(self, collection_name, add_search_component_json):
    print "Adding search component {}".format(add_search_component_json["name"])
    add = {"add-searchcomponent": add_search_component_json}
    replace = {"update-searchcomponent": add_search_component_json}
    return self.add_config(collection_name, add_search_component_json, add, replace)


  def add_request_handler(self, collection_name, add_req_handler_json):
    print "Adding request handler {}".format(add_req_handler_json["name"])
    add = {"add-requesthandler": add_req_handler_json}
    replace = {"update-requesthandler": add_req_handler_json}

    return self.add_config(collection_name, add_req_handler_json, add, replace)


  def add_config(self, collection_name, original, add, replace):
    resp = self.admin_session.post("apollo/solr/{0}/config".format(collection_name),
                                   data=json.dumps(add))
    errors = self.check_bulk_api_for_errors(resp.json())
    if resp.status_code != 200 or errors:
      print "Couldn't create config, trying replace {0}".format(original["name"])
      resp = self.admin_session.post("apollo/solr/{0}/config".format(collection_name),
                                     data=json.dumps(replace))
      errors = self.check_bulk_api_for_errors(resp.json())
      if resp.status_code != 200 or errors:
        print "Unable to create config: {0}".format(resp.text)
        return False
      else:
        print "Replaced config {0}".format(original["name"])
    else:
      print "Added config"
    return True

  def remove_request_handler(self, collection_name, req_handler_name):
    print "Attempting removal of request handler: {0}".format(req_handler_name)
    remove = {
      "delete-requesthandler": req_handler_name
    }
    resp = self.admin_session.post("apollo/solr/{0}/config".format(collection_name),
                                   data=json.dumps(remove))
    errors = self.check_bulk_api_for_errors(resp.json())
    if resp.status_code != 200 or errors:
      print "Couldn't remove req handler: {0}".format(req_handler_name)
      print errors
      return False
    else:
      print "Removed req handler {0}".format(req_handler_name)
    return True

  def remove_search_component(self, collection_name, component_name):
    print "Attempting removal of search component: {0}".format(component_name)
    remove = {
      "delete-searchcomponent": component_name
    }
    resp = self.admin_session.post("apollo/solr/{0}/config".format(collection_name),
                                   data=json.dumps(remove))
    errors = self.check_bulk_api_for_errors(resp.json())
    if resp.status_code != 200 or errors:
      print "Couldn't remove search component: {0}".format(component_name)
      print errors
      return False
    else:
      print "Removed search comp {0}".format(component_name)
    return True


  #Returns None if there are no errors, else a list of the errors
  def check_bulk_api_for_errors(self, response_json):
    result = None
    #print response_json
    if "errorMessages" in response_json:
      #print response_json["errorMessages"]
      result = response_json["errorMessages"]
    return result

  def send_signal(self, collection_id, payload, req_headers=None):
    """
    Send a signal
    """
    resp = self.app_session.get("apollo/signals/{0}/i".format(collection_id),
                                # tack on the i so that we invoke the snowplow endpoint
                                params=payload, headers=req_headers)
    if resp.status_code != 200:
      print "Unable to send signal: {0}".format(resp.text)
      return False
    return True

  def get_role(self, rolename):
    resp = self.admin_session.get("roles")
    if resp.status_code == 200:
      for role in resp.json():
        if role["name"] == rolename:
          return role
    else:
      print "Unable to find roles"
      return None

  def update_role(self, rolename, data):
    role = self.get_role(rolename)
    if role:
      for key in data:
        print "Adding/Updating {0} with {1}".format(key, data[key])
        role[key] = data[key]
      print role
      resp = self.admin_session.put("roles/{0}".format(role["id"]), data=json.dumps(role), headers={'Content-Type': "application/json"})
      if resp.status_code != 200:
        print "Unable to send signal: {0}".format(resp.text)
        return False
      return True
    return False


  def create_user(self, username, password, roles=None):
    resp = self.admin_session.get("users")
    exists = False
    for user in resp.json():
      if user['username'] == username:
        exists = True
        break
    if not exists:
      # Create User
      if not roles:
        roles = ["search"]
      print("Creating %s user... " % username)
      resp = self.admin_session.post("users",
                                     data=json.dumps({
                                       "username": username,
                                       "password": password,
                                       "passwordConfirm": password,  # TODO: don't hardcode this
                                       "realmName": "native",
                                       "roleNames": roles  # TODO figure out correct permissions
                                     }),
                                     headers={'Content-Type': "application/json"})
      if resp.status_code == 201:
        print("ok")
      else:
        print("failed")
        print(resp.text)
        return False
    else:
      # User exists
      print("User %s exists, doing nothing" % username)
    return True

  def create_collection(self, collection_id, enable_signals=False, enable_search_logs=True, enable_dynamic_schema=True, solr_params=None, default_commit_within=10000):
    resp = self.admin_session.get("apollo/collections/{0}".format(collection_id))
    if resp.status_code == 404:
      # Create
      print("Creating Collection {0}... ".format(collection_id))
      config_data = {'id': collection_id, 'commitWithin': default_commit_within}
      if solr_params:
        config_data["solrParams"] = solr_params
      print(config_data)
      resp = self.admin_session.post("apollo/collections", data=json.dumps(config_data),
                                     headers={'Content-Type': "application/json"})
      if resp.status_code == 200:
        print("ok")
        if enable_signals:
          print "Enabling Signals"
          sig_resp = self.admin_session.put("apollo/collections/{0}/features/signals".format(collection_id),
                                            data='{"enabled":true}',
                                            headers={'Content-Type': "application/json"})
          print sig_resp.status_code
        if enable_search_logs:
          self.admin_session.put("apollo/collections/{0}/features/searchLogs".format(collection_id),
                                 data='{"enabled":true}',
                                 headers={'Content-Type': "application/json"})
        if enable_dynamic_schema:
          self.admin_session.put("apollo/collections/{0}/features/dynamicSchema".format(collection_id),
                                 data='{"enabled":true}',
                                 headers={'Content-Type': "application/json"})
      else:
        print("failed")
        print(resp.text)
        return False
    elif resp.status_code == 200:
      print("Collection {0} exists, doing nothing".format(collection_id))
    else:
      print("Collection API error, aborting")
      print(resp.text)
      return False
    return True

  def create_query_profile(self, collection_id, name, pipeline_name):

    resp = self.admin_session.put("apollo/collections/{0}/query-profiles/{1}".format(collection_id, name),
                                  data= pipeline_name ,
                                  headers={"Content-type": "text/plain"})

    if resp.status_code != 204:
      print "Problem creating query profile: {0}, {1}".format(resp.status_code, resp.json())
    return resp

  def create_pipeline(self, pipeline_config, pipe_type="index-pipelines"):
    id = pipeline_config["id"]
    print "create pipeline: " + id
    resp = self.admin_session.put("apollo/{0}/{1}".format(pipe_type, id), data=json.dumps(pipeline_config),
                                  headers={"Content-type": "application/json"})

    if resp.status_code != 200:
      print resp.status_code, resp, json.dumps(pipeline_config)
      return resp
    resp = self.admin_session.put("apollo/{0}/{1}/refresh".format(pipe_type, id),
                                  headers={"Content-type": "application/json"})
    if resp.status_code != 204:
      print resp.status_code, resp.json()
    return resp

  def create_batch_job(self, batch_job_config):
    id = batch_job_config["id"]
    print "create batch job: " + id
    resp = self.admin_session.put("apollo/spark/configurations/{0}".format(id), data=json.dumps(batch_job_config),
                                  headers={"Content-type": "application/json"})
    if resp.status_code != 200:
      print resp.status_code, resp.json()
    return resp

  def create_experiment(self, experiment_config):
    id = experiment_config["id"]
    print "create experiment: " + id
    success = False
    resp = self.admin_session.post("apollo/experiments/configs", data=json.dumps(experiment_config),
                                   headers={"Content-type": "application/json"})

    if resp.status_code != 200:

      if resp.status_code == 409:#try a PUT
        print "Trying PUT"
        resp = self.admin_session.put("apollo/experiments/configs/{0}".format(id), data=json.dumps(experiment_config),
                                      headers={"Content-type": "application/json"})

        if resp.status_code != 200:
          print resp.status_code, resp.json()
        else:
          success = True
      else:
        print resp.status_code, resp.json()
    else:
      success = True
      success = True

    if success:
      #start the job
      print "Starting {} experiment".format(id)
      resp = self.admin_session.post("apollo/experiments/jobs/{0}".format(id), data=None)
      if resp.status_code != 200:
        print "Unable to start job"
        print resp.status_code, resp.json()


    return resp

  def create_or_update_datasources(self, project, includeJIRA=False):
    twitter_config = None
    jira_config = None
    mailbox_configs = []
    wiki_configs = []
    website_configs = []
    github_configs = []
    stack_configs = []
    # Generate twitter datasources
    if "twitter" in project and app.config.get('TWITTER_CONSUMER_KEY'):
      twitter_config = create_twitter_datasource_configs(project)
      # print twitter_config['id']
      if twitter_config:
        self.update_datasource(**twitter_config)
    # JIRA
    if includeJIRA:
      if "jira" in project:
        jira_config, sched = create_jira_datasource_config(project)
        self.update_datasource(**jira_config)
        self.create_or_update_schedule(sched)
    # Generate Mailboxes
    if "mailing_lists" in project:
      mailbox_configs, schedules = create_mailinglist_datasource_configs(project)
      for config in mailbox_configs:
        self.update_datasource(**config)
      for schedule in schedules:
        self.create_or_update_schedule(schedule)
    # Generate Wikis
    if "wikis" in project:
      wiki_configs, schedules = create_wiki_datasource_configs(project)
      for config in wiki_configs:
        self.update_datasource(**config)
      for schedule in schedules:
        self.create_or_update_schedule(schedule)
    # Generate Githubs
    if "githubs" in project:
      github_configs, schedules = create_github_datasource_configs(project)
      for config in github_configs:
        self.update_datasource(**config)
      for schedule in schedules:
        self.create_or_update_schedule(schedule)
    # Generate Websites
    if "websites" in project:
      website_configs, schedules = create_website_datasource_configs(project)
      for config in website_configs:
        self.update_datasource(**config)
      for schedule in schedules:
        self.create_or_update_schedule(schedule)
    if "stacks" in project:
      stack_configs, schedules = create_stack_datasource_configs(project)
      for config in stack_configs:
        self.update_datasource(**config)
      for schedule in schedules:
        self.create_or_update_schedule(schedule)
    #TODO: should we return schedules?
    # TODO: flatten this out
    # Add in the PUTS
    return (twitter_config, jira_config, mailbox_configs, wiki_configs, website_configs, github_configs, stack_configs)





  def _from_solr_doc(self, solr_doc):
    """
    Convert a document coming back from Solr to
    """
    return Document(id=solr_doc.get("id"), author=solr_doc.get("author"), source=solr_doc.get("source"),
                    project=solr_doc.get("project"), content=solr_doc.get("content"),
                    created_at=solr_doc.get("created_at"), link=solr_doc.get("link"))

  def get_document(self, doc_id):
    path = "apollo/query-pipelines/{1}/collections/{2}/select".format("default", "lucidfind")
    params = {
      "q": "*:*",
      "fq": "id:{0}".format(doc_id),
      "wt": "json"
    }
    resp = self.app_session.get(path, params=params, headers={"Content-type": "application/json"})
    return self._from_solr_doc(resp.json()['response']['docs'][0])

  def get_user(self, username, email=""):
    path = "apollo/collections/{0}/query-profiles/{1}/select".format("users", "default")
    params = {
      "q": "username:\"{0}\" OR email:\"{1}\"".format(username, email),
      "fq": [],
      "rows": 1,
      "start": 0,
      "wt": "json"
    }
    resp = self.admin_session.get(path, params=params, headers={"Content-type": "application/json"})

    decoded = resp.json()
    docs = decoded['response']['docs']

    return docs

  def add_user(self, user_data):
    path = "apollo/index-pipelines/users-default/collections/users/index"
    data = {"fields": []}
    for field in user_data:
      data["fields"].append({"name": field, "value": user_data[field]})
    records = [data]
    resp = self.admin_session.post(path,
                                   data=json.dumps(records),
                                   headers={"Content-type": "application/json"})
    if resp.status_code == 200:
      return True
    else:
      print resp.status_code
      print resp.text
      raise Exception("Couldn't add user to users collection")
    return False

  def delete_taxonomy(self, collection_id, category=None):
    if category:
      resp = self.admin_session.delete("apollo/collections/{0}/taxonomy/{1}".format(collection_id, category))
      print resp.status_code
    else:
      # get all the categories at the top and delete them
      resp = self.admin_session.get("apollo/collections/{0}/taxonomy".format(collection_id))
      if resp.status_code == 200:
        tax = resp.json()
        for category in tax:
          print "Deleting: {0}".format(category["id"])
          resp = self.admin_session.delete("apollo/collections/{0}/taxonomy/{1}".format(collection_id, category["id"]))
      elif resp.status_code == 404:
        pass  # do nothing, as there is no taxonomy
      else:
        raise Exception("Couldn't get {1} taxonomy for {0}".format(collection_id, resp.status_code))

  def create_taxonomy(self, collection_id, taxonomy):
    print "Creating taxonomy for {0}".format(collection_id)

    resp = self.admin_session.post("apollo/collections/{0}/taxonomy".format(collection_id), data=json.dumps(taxonomy),
                                   headers={"Content-type": "application/json"})
    if resp.status_code == 404:
      return None
    elif resp.status_code == 200:
      return resp.json()
    else:
      print resp.status_code
      print resp.text
      raise Exception("Couldn't create taxonomy for {0}.  Tax: {1}".format(collection_id, taxonomy))



  def update_logging_scheduler(self):
    delete_old_logs_json = {
      "id":"delete-old-logs",
      "creatorType":"system",
      "creatorId":"DefaultLogCleanupScheduleRegistrar",
      "createTime":"2016-10-06T17:03:43.792Z",
      "startTime":"2016-10-06T17:03:43.792Z",
      "repeatUnit":"DAY",
      "interval":"1",
      "active":"true",
      "callParams":{
        "uri":"solr://logs/update",
        "method":"GET",
        "queryParams":{
          "wt":"json",
          "stream.body":"<delete><query>timestamp_tdt:[* TO NOW-1DAYS] OR timestamp_dt:[* TO NOW-1DAYS]</query></delete>"
        },
        "headers":{

        }
      }
    }
    start_value = self.admin_session.get("apollo/scheduler/schedules/delete-old-logs")
    try:
      start_value.raise_for_status()
      start_status = start_value.status_code
      if (start_status == 404):
        print("We have to create a new delete-old-logs schedule")
        final_value = self.admin_session.post("apollo/scheduler/schedules/delete-old-logs", data=json.dumps(delete_old_logs_json))
      else:
        print("We have to update the existing delete-old-logs schedule")
        final_value = self.admin_session.put("apollo/scheduler/schedules/delete-old-logs", data=json.dumps(delete_old_logs_json))

      final_value.raise_for_status()

    except:
      print("ERROR: Failed to update the delete logs schedule")

    else:
      print("SUCCESS: We have updated the delete logs schedule")


  def create_or_update_schedule(self, schedule):
    # check to see if it exists already
    resp = self.admin_session.get("apollo/scheduler/schedules/{0}".format(schedule["id"]))
    if resp.status_code == 200:
      print "Updating schedule for {0}".format(schedule["id"])
      resp = self.admin_session.put("apollo/scheduler/schedules/{0}".format(schedule["id"]), data=json.dumps(schedule),
                                    headers={"Content-type": "application/json"})
      if resp.status_code == 204:
        return None  #TODO: better code here?
      else:
        print resp.status_code
        print resp.text
        raise Exception("Couldn't update schedule for {0}.  Schedule: {1}".format(schedule["id"], schedule))
    elif resp.status_code == 404:
      print "Creating schedule for {0}".format(schedule["id"])
      resp = self.admin_session.post("apollo/scheduler/schedules", data=json.dumps(schedule),
                                     headers={"Content-type": "application/json"})
      if resp.status_code == 200:
        return resp.json()
      else:
        print resp.status_code
        print resp.text
        raise Exception("Couldn't create schedule for {0}.  Schedule: {1}".format(schedule["id"], schedule))
    return None

  #if schedules is none, then activate all.  If specified, only activate those schedules that match
  # schedules is an array of schedule names to activate
  # if searchHubOnly is false, then activate all schedules regardless if SearchHub created them
  def activate_schedules(self, schedules=None, searchHubOnly=True):
    self.update_schedules(schedules, searchHubOnly, True)

  def stop_schedules(self, schedules=None, searchHubOnly=True):
    self.update_schedules(schedules, searchHubOnly, False)

  def update_schedules(self, schedules=None, searchHubOnly=True, active=True):
    if not schedules:
      schedules = []
    #get the list of schedules
    resp = self.admin_session.get("apollo/scheduler/schedules")
    if resp.status_code == 200:
      server_schedules = resp.json()
      for schedule in server_schedules:
        if schedule["active"] != active:
          if len(schedules) > 0 and schedule["id"] not in schedules:
            print "skipping starting {0}".format(schedule["id"])
            continue
          schedule["active"] = active
          if searchHubOnly and not schedule["id"].startswith("schedule-") and not schedule["id"].startswith("suggester-"):
            print "skipping starting {0}".format(schedule["id"])
            continue
          print "Setting schedule {0} active flag to {1}".format(schedule["id"], active)
          self.create_or_update_schedule(schedule)

    else:
      print resp.status_code
      print resp.text
      raise Exception("Couldn't get list of schedules")
    return None
  def get_datasource(self, id):
    resp = self.admin_session.get("apollo/connectors/datasources/{0}".format(id))
    if resp.status_code == 404:
      return None
    elif resp.status_code == 200:
      return resp.json()

  def update_datasource(self, id, **config):
    """
    Update a datasource if it has changed
    """
    datasource = self.get_datasource(id)
    config['id'] = id

    if datasource is None:
      # Create it
      resp = self.admin_session.post("apollo/connectors/datasources",
                                     data=json.dumps(config),
                                     headers={"Content-type": "application/json"})
      if resp.status_code != 200:
        raise Exception("Could not create Datasource %s: %s \n%s" % (id, resp.text, json.dumps(config)))
    else:
      # Update it (maybe)
      if compare_datasources(config, datasource) == False:
        print("Detected an update in config, updating Fusion")
        resp = self.admin_session.put("apollo/connectors/datasources/{0}".format(id),
                                      data=json.dumps(config),
                                      headers={"Content-type": "application/json"})
        # TODO check response

  def start_datasource(self, id):
    datasource = self.get_datasource(id)
    if datasource is not None:
      resp = self.admin_session.post("apollo/connectors/jobs/{0}".format(id))
      return resp.json()
    else:
      raise Exception("Could not start Datasource %s" % (id))

  #Stop all datasources
  def stop_datasources(self):
    #get a list of all the datasources
    resp = self.admin_session.get("apollo/connectors/datasources")
    if resp.status_code == 200:
      json = resp.json()
      for ds in json:
        print "Stopping {0}".format(ds["id"])
        self.stop_datasource(ds["id"])
    else:
      raise Exception("Unable to retrieve datasource list")

  def stop_datasource(self, id, abort=False):
    datasource = self.get_datasource(id)
    if datasource is not None:
      resp = self.admin_session.delete("apollo/connectors/jobs/{0}?abort={1}".format(id, str(abort).lower()))
      return resp.json()



def compare_datasources(test_datasource, target_datasource):
  """
  Test if test_datasource is a subset of target_datasource

  :param test_datasource: the datasource to test
  :param target_datasource: the target datasource for comparison with
  :returns: True if test_datasource is a subset of target_datasource, False otherwise
  """

  is_subset = True
  for change in diff(test_datasource, target_datasource):
    if change[0] != "add":
      is_subset = False
      break
  return is_subset