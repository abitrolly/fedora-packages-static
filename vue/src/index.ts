import Vue from "vue";
import Datagrepper from "./Datagrepper.vue";

function init(): void {
    const packageName = /\/pkgs\/(.+)\/.+\//.exec(window.location.pathname);
    if (!packageName) {
        console.error("Could not find package name!");
        return;
    }

    // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
    Vue.prototype.$package = packageName[1];

    new Vue({
        el: "#vue",
        components: {
            Datagrepper
        }
    });
}

init();
