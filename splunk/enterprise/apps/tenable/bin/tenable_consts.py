import import_declare_test
import os

verify_ssl_for_ot = True
verify_ssl_for_sc_cert = True
verify_ssl_for_sc_api_key = True
verify_ssl_for_sc_creds = True

ta_accounts_conf = 'ta_tenable_account'

ACCOUTNS_CONF_LOCAL_PATH = os.path.join(os.environ.get('SPLUNK_HOME'), 'etc', 'apps', import_declare_test.ta_name, 'local', 'ta_tenable_account.conf')

CUSTOM_CERT_FILE_LOC = os.path.join(os.environ.get('SPLUNK_HOME'), 'etc', 'apps', import_declare_test.ta_name, 'local', 'custom_certs', 'custom_cert_{}.pem')