// Copyright (c) Microsoft. All rights reserved.
// Standalone WebRTC experience entry point. Separate bundle from the integrated demo
// (main.jsx) so this page can be shipped/embedded on its own while reusing the shared
// config, session hook, agent catalog, and message rendering.

import { createRoot } from "react-dom/client";
import { WebRtcApp } from "./WebRtcApp.jsx";
import "./webrtc.css";

createRoot(document.getElementById("root")).render(<WebRtcApp />);
