<template>
  <div>
    <h3>Recent Activity</h3>
    <div v-if="state === State.error">{{ errMsg }}</div>
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
    <div v-if="state === State.loading" class="d-flex justify-content-center">
      <div class="spinner"></div>
    </div>
    <div v-if="state === State.requestLoadMore">
      No {{ messages.length ? "more" : "" }} activity from the past month. <span class="btn-link" @click="setDeltaToYear()">Load more activity</span>
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
  requestLoadMore
}

enum Time {
  week = 604800,
  month = 2.628e+6,
  year = 3.154e+7
}

export default Vue.extend({
  data() {
    return {
      // UI
      state: State.loading,
      errMsg: "",
      State,
      // Data from DG
      messages: [] as Messages[],
      pages: 0,
      currentPage: 0,
      count: 0,
      // To control DG queries
      end: Math.round(Date.now() / 1000),
      delta: Time.week,
      firstLoad: true
    };
  },
  mounted() {
    this.loadPage();
    this.setupObserver();
  },
  methods: {
    async loadPage(removedDelta?: boolean) {
      this.state = State.loading

      const dgParamaters = this.findDgParams(removedDelta);
      if (dgParamaters?.noLoad) {
        return;
      }
      const dgData = await dgConnector.getMessages(
        this.$package,
        dgParamaters
      );
      if (typeof dgData !== "object") {
        // There really isn't a good way to stop a request on page unload...
        const ignoredErrors = [
          "TypeError: NetworkError when attempting to fetch resource."
        ];
        console.log(dgData)
        if (!ignoredErrors.includes(dgData)) {
          this.errMsg = dgData;
          this.state = State.error;
        }
        return;
      }

      this.messages = this.messages.concat(dgData.messages);
      this.pages = dgData.pages;
      this.currentPage = dgData.page;
      this.count = dgData.count;

      this.firstLoad = false;
      this.state = State.idle;

      // Try to load more if we aren't able to find anything on inital load
      if (this.count === 0) {
        this.loadPage()
      }
    },
    findDgParams(changedDelta?: boolean): { delta: number; end: number; page: number } | { noLoad: true } {
      /*
        Find the delta, page, and end paramaters for dg queries.
        Incements the page if there are more pages. Otherwise,
        Changes delta to a month if nothing found in a week or no more pages.
        If that runs out/has no data, then prompts user to load a year of dg data.
      */
      let page = this.currentPage;
      if (this.currentPage < this.pages) {
        page += 1;
      // make sure at least one request has been made before changing delta
      } else if (!this.firstLoad) {
        if (this.delta === Time.week) {
          this.end -= Time.week;
          this.delta = Time.month;
          page = 1
        } else if (this.delta === Time.month) {
          // Request to load more results
          this.state = State.requestLoadMore;
          this.loadNextPage = this.count !== 0;
          return { noLoad: true };
        } else if (changedDelta) {
          // Delta just changed to a year, reset pagination
          page = 1
        } else {
          // No more results
          this.state = State.idle
          return { noLoad: true };

        }
      }

      return {
        page,
        end: this.end,
        delta: this.delta
      }
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

      if (!entries[0].isIntersecting) {
        return;
      }

      await this.loadPage();
    },
    setDeltaToYear() {
      this.delta = Time.year;
      this.end -= Time.month;
      this.loadPage(true)
    }
  },
});
</script>
