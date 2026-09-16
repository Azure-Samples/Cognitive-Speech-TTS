// Copyright (c) Microsoft. All rights reserved.
// React entry point.

import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import "./studio.css";

createRoot(document.getElementById("root")).render(<App />);
