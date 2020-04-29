import Vue from "vue";
import Datagrepper from "./Datagrepper.vue";

function init(): void {
    const packageName = window.location.pathname.match(/\/pkgs\/(.+)\//);
    if (!packageName) {
        console.error("Could not find package name!");
        return;
    }

    Vue.prototype.$package = packageName[1];

    new Vue({
        el: "#vue",
        components: {
            Datagrepper
        }
    });
}

init();
