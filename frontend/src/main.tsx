import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import NavigationApp from "./NavigationApp";
import "./styles/global.css";

const RootApp = new URLSearchParams(window.location.search).get("view") === "navigation" ? NavigationApp : App;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RootApp />
  </React.StrictMode>
);
