# metsis-solr-configset

![Create SolR core](https://img.shields.io/github/actions/workflow/status/metno/metsis-solr-configset/solr.yml?branch=master&label=solrcore)
![Xml-lint](https://img.shields.io/github/actions/workflow/status/metno/metsis-solr-configset/xmllint.yml?branch=master&label=xmllint)

This repository contains Solr configset and solr schema for indexing MMD files. Atomic updates are supported.
This repo should always be compatible with the latest [release](https://github.com/metno/mmd/releases) of the
[MMD specification](https://github.com/metno/mmd).

Tagging releases from this repository should follow the versioning from the MMD repository.

## Releases

### Latest release

![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/metno/metsis-solr-configset)

### Previous releases

- v3.5.3-solr9 - 2025-08-28 - For Solr 9.10 MMD v3.4
- v3.4-solr9 - 2023-02-10 - For Solr 9.1 MMD v3.4
- v3.4-solr8 - 2023-02-10 - For Solr 8.11 MMD v3.4

### Tools - upload_config.py

This script uploads this schema configset to a given Solr cloud.

|Argument       |Description                                               | Required|
|:--------------|----------------------------------------------------------|--------:|
| --user        | The Solr username for authentication.                    | Yes     |
| --url         | The Solr Cloud base url (e.g., <<http://solr:8983>).     |  Yes    |
| --config-name | The name of the configset to be upladed (e.g. adc-4.1.0).|  Yes    |
| --source-dir  | Path to the directory to compress (default: 'conf')      | No      |

Example: `./upload_config.py --user solr --url http://solr:8983 --config-name adc-4.1.0`
