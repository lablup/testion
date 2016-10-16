# testion
A simple CI server for us


## Installation

You need to install this inside a virtualenv where your target project's
dependencies are installed.

Simply run `python setup.py install` then.

If you encounter errors while installing `uritemplate` package, then
manually install `github3.py` package using pip and retry.
There is a temporary issue due to renaming of `uritemplate` package
which is not handeld in the stable version of `github3.py` package.

If you encounter errors like:
`Failed to resolve address for https: Name or service not known`
then your libgit2 installation does not support SSL.
In Debian Linux, you need to compile libgit2 manually to resolve
this issue due to [OpenSSL license conflicts](https://github.com/libgit2/pygit2/issues/644).

## Configuration

Testion requires the following environment variables:

 * `GH_USERNAME` for GitHub login.
 * `GH_TOKEN` for GitHub login (substitute for passwords)

Additionally, it needs the followings to upload logs to AWS S3:

 * `AWS_ACCESS_KEY_ID`
 * `AWS_SECRET_ACCESS_KEY`
 * `AWS_DEFAULT_REGION`

There is no separate configuration file yet, so the behavior of each test
reporter is fixed.

UnitTestReporter runs `manage.py test --noinput <all-subdirs-except-"functional_tests">`.
It excludes `.git` and Python's cache directories from the subdir list.

SeleniumFunctionalTestReporter runs `manage.py test --noinput functional_tests`
for recently updated branches (within last 24 hours) with a Selenium sever.

## Running

`python -m testion.server -p <port>` opens an HTTP server accepting webhook
requests on the given port.

The webhook URL is `http://<hostname>:<port>/webhook?report_type=<type>`
where type is either `unit` (unit tests) or `slfunc` (functional tests with
a selenium server).
It expects `X-Github-Event: push` header and a JSON-formatted body as
[described here](https://developer.github.com/v3/activity/events/types/#pushevent)
with the `POST` method.
