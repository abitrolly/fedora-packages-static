const path = require("path");
const VueLoaderPlugin = require("vue-loader/lib/plugin");
const ForkTsCheckerWebpackPlugin = require("fork-ts-checker-webpack-plugin");

module.exports = {
  mode: "development",
  devtool: "source-map",
  entry: "./src/index.ts",
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        loader: "ts-loader",
        options: {
          appendTsSuffixTo: [/\.vue$/],
          transpileOnly: true
        },
        exclude: /node_modules/
      },
      {
        test: /\.vue$/,
        loader: "vue-loader"
      }
    ]
  },
  plugins: [
    new VueLoaderPlugin(),
    new ForkTsCheckerWebpackPlugin()
  ],
  resolve: {
    extensions: [
      ".js",
      ".jsx",
      ".vue",
      ".json",
      ".ts",
      ".tsx"
    ],
    modules: ["node_modules"],
    alias: {
      'vue$': 'vue/dist/vue.esm.js'
    }
  }
};
