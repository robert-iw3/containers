class AccountHook {

    /**
     * Form hook
     * @constructor
     * @param {Object} globalConfig - Global configuration.
     * @param {string} serviceName - Service name
     * @param {object} state - Initial state of the form
     * @param {string} mode - Form mode. Can be edit, create or clone
     * @param {object} util - Object containing utility methods
     * {
     *    setState,
     *    setErrorMsg,
     *    setErrorFieldMsg,
     *    clearAllErrorMsg
     * }
     **/
    constructor(globalConfig, serviceName, state, mode, util) {
        this.globalConfig = globalConfig;
        this.serviceName = serviceName;
        this.state = state;
        this.mode = mode;
        this.util = util;
    }
    isTrue(val) {
        var value = String(val).trim().toUpperCase();
        if (value === "1" || value === "TRUE") {
            return true;
        }
        return false;
    }

    onChange(field, value, dataDict) {
        if (field == "tenable_account_type") {
            this.manageFieldsForAccountType(value);
        } else if (field == "proxy_enabled") {
            this.manageFieldsForProxyType(value);
        } else if (field == "use_ca_cert") {
            this.manageCustomCert(dataDict);
        }
    }

    manageCustomCert(dataDict) {
        const enableCaCert = this.isTrue(dataDict.data.use_ca_cert.value);
        this.util.setState((prevState) => {
            const data = { ...prevState.data };
            data.custom_certificate.display = enableCaCert;
            return {data}
        });
    }

    manageFieldsForAccountType(onChangeSelectedAccountFieldValue) {
        const field = this.state.data;

        let flag = 0;
        let value = null;
        let isAccountType = false;

        if (onChangeSelectedAccountFieldValue) {
            value = onChangeSelectedAccountFieldValue;
            isAccountType = true;
        } else {
            isAccountType = field.tenable_account_type;
            value = field.tenable_account_type && field.tenable_account_type.value;
        }

        if (isAccountType) {
            switch (value) {
                case "tenable_io":
                    flag = 0;
                    break;
                case "tenable_securitycenter_credentials":
                    flag = 1;
                    break;
                case "tenable_securitycenter_certificate":
                    flag = 2;
                    break;
                case "tenable_securitycenter_api_keys":
                    flag = 3;
                    break;
                case "tenable_ot_security_icp":
                    flag = 4;
                    break;
                case "tenable_asm":
                    flag = 5;
                    break;
                default:
                    flag = 6;
                    break;
            }
        }

        this.util.setState((prevState) => {
            let data = { ...prevState.data };
            data.access_key.display = false;
            data.secret_key.display = false;
            data.username.display = false;
            data.password.display = false;
            data.certificate_path.display = false;
            data.key_file_path.display = false;
            data.key_password.display = false;
            data.api_secret.display = false;
            data.tenable_sc_access_key.display = false;
            data.tenable_sc_secret_key.display = false;
            data.tenable_easm_domain.display = false;
            data.tenable_easm_api_key.display = false;
            data.use_ca_cert.display = false;
            data.custom_certificate.display = false;
            data.address.display = true;

            switch (flag) {
                case 0:
                    data.access_key.display = true;
                    data.secret_key.display = true;
                    data.use_ca_cert.display = false;
                    data.custom_certificate.display = false;
                    break;
                case 1:
                    data.username.display = true;
                    data.password.display = true;
                    data.use_ca_cert.display = true;
                    break;
                case 2:
                    data.certificate_path.display = true;
                    data.key_file_path.display = true;
                    data.key_password.display = true;
                    data.tenable_sc_access_key.display = true;
                    data.tenable_sc_secret_key.display = true;
                    data.use_ca_cert.display = true;
                    break;
                case 3:
                    data.tenable_sc_access_key.display = true;
                    data.tenable_sc_secret_key.display = true;
                    data.use_ca_cert.display = true;
                    break;
                case 4:
                    data.api_secret.display = true;
                    data.use_ca_cert.display = true;
                    break;
                case 5:
                    data.address.display = false;
                    data.tenable_easm_domain.display = true;
                    data.tenable_easm_api_key.display = true;
                    data.use_ca_cert.display = false;
                    data.custom_certificate.display = false;
                    break;
                default:
                    data.api_secret.display = true;
                    break;
            }

            if (onChangeSelectedAccountFieldValue) {
                if (value == "tenable_io") {
                    data.address.value = "cloud.tenable.com";
                    data.address.disabled = false;
                    data.username.value = "";
                    data.password.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                    data.tenable_easm_api_key.value = "";
                    data.tenable_easm_domain.value = "";
                } else if (value == "tenable_securitycenter_credentials") {
                    data.address.value = "";
                    data.address.disabled = false;
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                    data.tenable_easm_api_key.value = "";
                    data.tenable_easm_domain.value = "";
                } else if (value == "tenable_securitycenter_certificate") {
                    data.address.value = "";
                    data.address.disabled = false;
                    data.username.value = "";
                    data.password.value = "";
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.tenable_easm_api_key.value = "";
                    data.tenable_easm_domain.value = "";
                } else if (value == "tenable_securitycenter_api_keys") {
                    data.address.value = "";
                    data.address.disabled = false;
                    data.username.value = "";
                    data.password.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.tenable_easm_api_key.value = "";
                    data.tenable_easm_domain.value = "";
                } else if (value == "tenable_ot_security_icp") {
                    data.address.value = "";
                    data.address.disabled = false;
                    data.username.value = "";
                    data.password.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                    data.tenable_easm_api_key.value = "";
                    data.tenable_easm_domain.value = "";
                } else if (value == "tenable_asm") {
                    data.address.value = "";
                    data.address.disabled = false;
                    data.username.value = "";
                    data.password.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                }
            }
            return { data };
        });
    }

    manageFieldsForProxyType(onChangeProxyFieldValue) {
        const field = this.state.data;

        let isProxyField = null;
        let proxyFieldValue = null;

        if (onChangeProxyFieldValue == "0" || onChangeProxyFieldValue == "1") {
            isProxyField = true;
            proxyFieldValue = onChangeProxyFieldValue;
        } else {
            isProxyField = field.proxy_enabled;
            proxyFieldValue = field.proxy_enabled.value;
        }

        if (isProxyField) {
            if (proxyFieldValue == "0") {
                this.hideProxyFields(onChangeProxyFieldValue);
            } else {
                this.showProxyFields();
            }
        }
    }

    showProxyFields() {
        this.util.setState((prevState) => {
            let data = { ...prevState.data };
            data.proxy_type.display = true;
            data.proxy_url.display = true;
            data.proxy_port.display = true;
            data.proxy_username.display = true;
            data.proxy_password.display = true;
            return { data };
        });
    }

    hideProxyFields(onChangeProxyFieldValue) {
        this.util.setState((prevState) => {
            let data = { ...prevState.data };
            data.proxy_type.display = false;
            data.proxy_url.display = false;
            data.proxy_port.display = false;
            data.proxy_username.display = false;
            data.proxy_password.display = false;

            if (onChangeProxyFieldValue == "0" || onChangeProxyFieldValue == "1") {
                data.proxy_url.value = "";
                data.proxy_port.value = "";
                data.proxy_username.value = "";
                data.proxy_password.value = "";
            }
            return { data };
        });
    }

    /*
        Put form validation logic here.
        Return ture if validation pass, false otherwise.
        Call displayErrorMsg when validtion failed.
    */
    onSave(dataDict) {
        this.util.setState((prevState) => {
            let data = { ...prevState.data };

            switch (dataDict.tenable_account_type) {
                case "tenable_io":
                    data.username.value = "";
                    data.password.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.api_secret.value = null;
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                    break;

                case "tenable_securitycenter_credentials":
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.api_secret.value = null;
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                    break;

                case "tenable_securitycenter_certificate":
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.username.value = "";
                    data.password.value = "";
                    data.api_secret.value = null;
                    break;

                case "tenable_securitycenter_api_keys":
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.username.value = "";
                    data.password.value = "";
                    data.api_secret.value = null;
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    break;

                case "tenable.ot":
                    data.username.value = "";
                    data.password.value = "";
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                    break;

                case "tenable_ot_security_icp":
                    data.username.value = "";
                    data.password.value = "";
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                    break;

                case "tenable_asm":
                    data.address.value = " ";
                    data.username.value = "";
                    data.password.value = "";
                    data.access_key.value = "";
                    data.secret_key.value = "";
                    data.certificate_path.value = "";
                    data.key_file_path.value = "";
                    data.key_password.value = "";
                    data.tenable_sc_access_key.value = "";
                    data.tenable_sc_secret_key.value = "";
                    break;

                default:
                    break;
            }

            return { data };
        });

        if (!dataDict.proxy_enabled || dataDict.proxy_enabled == "0") {
            this.util.setState((prevState) => {
                let data = { ...prevState.data };
                data.proxy_type.value = "";
                data.proxy_url.value = "";
                data.proxy_port.value = "";
                data.proxy_username.value = "";
                data.proxy_password.value = "";
                return { data };
            });
            return true;
        }

        if (!dataDict.proxy_type) {
            this.util.setErrorMsg('Proxy Type can not be empty');
            return false;
        }
        if (!dataDict.proxy_url) {
            this.util.setErrorMsg('Proxy Host can not be empty');
            return false;
        }
        if (!dataDict.proxy_port) {
            this.util.setErrorMsg('Proxy Port can not be empty');
            return false;
        }
        if (!dataDict.proxy_username ^!dataDict.proxy_password) {
            this.util.setErrorMsg('Please provide both proxy username and proxy password');
            return false;
        }
        return true;
    }

    /*
        Put logic here to execute javascript to be called after save success.
    */
    onSaveSuccess() {}

    /*
        Put logic here to execute javascript to be called on save failed.
    */
    onSaveFail() {}

    /*
        Put logic here to execute javascript after loading edit UI.
    */
    onEditLoad() {}

    /*
        Put logic here to execute javascript when UI gets rendered.
    */
    onRender() {
        this.manageFieldsForAccountType(null);
        this.manageFieldsForProxyType(null);
        var ca_cert = this.state.data.use_ca_cert.value;
        this.util.setState((prevState) => {
            let data = {
                ...prevState.data
            };
            if (this.isTrue(ca_cert)){
                data.custom_certificate.display = true;
            } else {
                data.custom_certificate.display = false;
            }
            return {data}
        });
    }
}

export default AccountHook;
