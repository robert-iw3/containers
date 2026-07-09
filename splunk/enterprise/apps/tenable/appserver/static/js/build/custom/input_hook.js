class InputHook {
    constructor(globalConfig, serviceName, state, mode, util) {
		this.globalConfig = globalConfig;
		this.serviceName = serviceName;
		this.state = state;
		this.mode = mode;
		this.util = util;
	}

	onRender() {
        if (this.mode === 'edit'){
            this.util.setState((prevState) => {
                const newState = { data: { ...prevState.data } };
                // disable the start_time field in edit mode
                if ("start_time" in newState.data == true) {
                    newState.data.start_time.disabled = true;
                }
                return newState;
            });
        }
	}
}

export default InputHook;
