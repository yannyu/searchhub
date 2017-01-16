import json
from schedule_helper import create_schedule

def create_website_datasource_configs(project):
  pipeline = project["website_pipeline"]
  if pipeline is None:
    pipeline = "website-default"
  configs = []
  schedules = []
  #TODO: should we have one crawler for all the websites under this project or one crawler per website?
  if "websites" in project:
    for web in project["websites"]:
      config, schedule = create_config(project["name"], project["label"], pipeline, web)
      configs.append(config)
      schedules.append(schedule)
  return configs, schedules


def create_config(project_name, project_label, pipeline, website):
  if "pipeline" in website:
    pipeline = website["pipeline"]  # individual mailing lists may override
  config = {
    'id': "website-{0}-{1}".format(project_name, website["name"]),
    "connector": "lucid.anda",
    "type": "web",
    'pipeline': pipeline,
    "parserId": "default",
    "properties": {
      "refreshOlderThan": -1,
      "f.appendTrailingSlashToLinks": False,
      "refreshErrors": False,
      "restrictToTreeIgnoredHostPrefixes": [
        "www."
      ],
      "dedupeSaveSignature": False,
      "crawlDBType": "in-memory",
      "f.discardLinkURLQueries": False,
      "f.respectMetaEquivRedirects": False,
      "fetchDelayMS": 50,
      "refreshAll": True,
      "f.defaultMIMEType": "application/octet-stream",
      "restrictToTreeAllowSubdomains": False,
      "maxItems": -1,
      "f.scrapeLinksBeforeFiltering": False,
      "dedupe": False,
      "f.allowAllCertificates": False,
      "collection": "lucidfind", #TODO: don't hardcode
      "forceRefresh": False,
      "f.obeyRobots": True,
      "fetchDelayMSPerHost": True,
      "indexCrawlDBToSolr": False,
      "fetchThreads": 1,
      "restrictToTree": True,
      "retainOutlinks": True,
      "f.defaultCharSet": "UTF-8",
      "emitThreads": 1,
      "excludeExtensions": [
        ".class",
        ".bin",
        ".jar"
      ],
      "diagnosticMode": False,
      "delete": True,
      "f.userAgentWebAddr": "",
      "initial_mapping": {
        "id": "FromMap",
        "mappings": [
          {"source": "project", "target": project_name, "operation": "set"},
          {"source": "project_label", "target": project_label, "operation": "set"},
          {"source": "datasource_label", "target": website["label"], "operation": "set"},
          {"source": "fetchedDate", "target": "publishedOnDate", "operation": "copy"},
          {"source": "isBot", "target": "false", "operation": "set"},
          {
            "source": "charSet",
            "target": "charSet_s",
            "operation": "move"
          },
          {
            "source": "fetchedDate",
            "target": "fetchedDate_dt",
            "operation": "move"
          },
          {
            "source": "lastModified",
            "target": "lastModified_dt",
            "operation": "move"
          },
          {
            "source": "signature",
            "target": "dedupeSignature_s",
            "operation": "move"
          },
          {
            "source": "contentSignature",
            "target": "signature_s",
            "operation": "move"
          },
          {
            "source": "length",
            "target": "length_l",
            "operation": "move"
          },
          {
            "source": "mimeType",
            "target": "mimeType_s",
            "operation": "move"
          },
          {
            "source": "parent",
            "target": "parent_s",
            "operation": "move"
          },
          {
            "source": "owner",
            "target": "owner_s",
            "operation": "move"
          },
          {
            "source": "group",
            "target": "group_s",
            "operation": "move"
          }
        ],
        "reservedFieldsMappingAllowed": False,
        "skip": False,
        "label": "field-mapping",
        "type": "field-mapping"
      },
      "restrictToTreeUseHostAndPath": True,
      "f.filteringRootTags": [
        "body",
        "head"
      ],
      "f.userAgentEmail": "",
      "f.timeoutMS": 10000,
      "failFastOnStartLinkFailure": True,
      "startLinks": [
        website["url"]
      ],
      "chunkSize": 100,
      "includeRegexes": [],
      "f.obeyRobotsDelay": True,
      "deleteErrorsAfter": -1,
      "f.userAgentName": "Lucidworks-Anda/2.0",
      "retryEmit": True,
      "depth": -1,
      "refreshStartLinks": False,
      "f.maxSizeBytes": 4194304,
      "aliasExpiration": 1
    }
  }
  if "excludes" in website:
    config['properties']['excludeRegexes'] = website["excludes"]
  if "includeRegexes" in website:
    config['properties']['includeRegexes'] = website["includeRegexes"]
  if "includeTags" in website:
    config['properties']['f.includeTags'] = website["includeTags"]
  if "excludeTags" in website:
    config['properties']['f.excludeTags'] = website["excludeTags"]
  if "includeTagIDs" in website:
    config['properties']['f.includeTagIDs'] = website["includeTagIDs"]
  if "excludeTagIDs" in website:
    config['properties']['f.excludeTagIDs'] = website["excludeTagIDs"]
  if "excludeTagClasses" in website:
    config['properties']['f.excludeTagClasses'] = website["excludeTagClasses"]
  if "scrapeLinksBeforeFiltering" in website:
    config['properties']['f.scrapeLinksBeforeFiltering'] = website["scrapeLinksBeforeFiltering"]
  if "restrictToTreeUseHostAndPath" in website:
    config['properties']['restrictToTreeUseHostAndPath'] = website["restrictToTreeUseHostAndPath"]
  if "multiurl" in website:
    config['properties']['startLinks'] = website["multiurl"]
  if "additional_mapping" in website:
    config['properties']['initial_mapping']['mappings'].append(website["additional_mapping"])
  if "additional_mapping_2" in website:
    config['properties']['initial_mapping']['mappings'].append(website["additional_mapping_2"])


  schedule = None
  if "schedule" in website:
    details = website["schedule"]
    schedule = create_schedule(details, config["id"])
  return config, schedule
