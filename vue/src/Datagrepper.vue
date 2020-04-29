<template>
  <div>
    <h2>Recent Activity</h2>
    <div v-if="errMsg">{{ errMsg }}</div>
    <div v-else-if="messages.length">
      <table class="table">
        <tbody>
          <tr v-for="message in messages" :key="message.id">
            <td><a :href="message.link"><img :src="message.icon" height="30" width="30"></a></td>
            <td>{{ message.subtitle }} <span style="color: grey;">{{ message.date }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else>Loading...</div>
    <div id="scrollTrigger"></div>
  </div>
</template>
<script lang="ts">
import Vue from "vue";
import {DgConnector, Messages} from "./datagrepper";

const dgConnector = new DgConnector("https://apps.fedoraproject.org/datagrepper");

export default Vue.extend({
  data() {
    return {
      errMsg: "",
      messages: [] as Messages[],
      pages: 0,
      currentPage: 0
    };
  },
  mounted() {
    this.loadPage();
    this.setupObserver();
  },
  methods: {
    async loadPage(page?: number) {
      const dgData = await dgConnector.getMessages(
        // @ts-ignore
        this.$package,
        { page }
      );
      if (typeof dgData !== "object") {
        this.errMsg = dgData;
        return;
      }

      this.messages = this.messages.concat(dgData.messages);
      this.pages = dgData.pages;
      this.currentPage = dgData.page;
    },
    setupObserver() {
      const observer = new IntersectionObserver(this.loadMore, { threshold: 1 });
      const scrollTrigger = document.querySelector('#scrollTrigger');
      if (scrollTrigger) {
        observer.observe(scrollTrigger);
      }
    },
    async loadMore(entries: IntersectionObserverEntry[]) {
      if (this.errMsg || !this.messages.length) {
        return;
      }

      if (this.currentPage === this.pages) {
        return;
      }

      if (!entries[0].isIntersecting) {
        return;
      }

      await this.loadPage(this.currentPage + 1);
    }
  },
});
</script>
