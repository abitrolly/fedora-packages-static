<template>
  <div>
    <h3>Recent Activity</h3>
    <div v-if="state == State.error">{{ errMsg }}</div>
    <div v-else-if="messages.length">
      <table class="table">
        <tbody>
          <tr v-for="message in messages" :key="message.id">
            <td><a :href="message.link"><img :src="message.icon" height="30" width="30"></a></td>
            <td>{{ message.subtitle }} <span class="text-muted">{{ message.date }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="state == State.loading" class="d-flex justify-content-center">
      <div class="spinner"></div>
    </div>
    <div id="scrollTrigger"></div>
  </div>
</template>
<script lang="ts">
import Vue from "vue";
import {DgConnector, Messages} from "./datagrepper";

const dgConnector = new DgConnector("https://apps.fedoraproject.org/datagrepper");

enum State {
  loading,
  idle,
  error,
  pageUnloading
}

export default Vue.extend({
  data() {
    return {
      state: State.loading,
      errMsg: "",
      messages: [] as Messages[],
      pages: 0,
      currentPage: 0,
      State
    };
  },
  created() {
    document.addEventListener('beforeunload', this.unloadHandler)
  },
  mounted() {
    this.loadPage();
    this.setupObserver();
  },
  methods: {
    async loadPage(page?: number) {
      this.state = State.loading
      const dgData = await dgConnector.getMessages(
        // @ts-ignore
        this.$package,
        { page }
      );
      if (typeof dgData !== "object") {
        if (this.state != State.pageUnloading) {
          this.errMsg = dgData;
          this.state = State.error
        }
        return;
      }

      this.messages = this.messages.concat(dgData.messages);
      this.pages = dgData.pages;
      this.currentPage = dgData.page;
      this.state = State.idle
    },
    setupObserver() {
      const observer = new IntersectionObserver(this.loadMore, { threshold: 1 });
      const scrollTrigger = document.querySelector('#scrollTrigger');
      if (scrollTrigger) {
        observer.observe(scrollTrigger);
      }
    },
    async loadMore(entries: IntersectionObserverEntry[]) {
      if (this.state != State.idle) {
        return;
      }

      if (this.currentPage === this.pages) {
        return;
      }

      if (!entries[0].isIntersecting) {
        return;
      }

      await this.loadPage(this.currentPage + 1);
    },
    unloadHandler() {
      this.state = State.pageUnloading
    }
  },
});
</script>
