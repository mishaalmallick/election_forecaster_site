import { BrowserRouter } from "react-router-dom";
import Overview from "./pages/Overview";

export default function App() {
  return (
    <BrowserRouter>
      <Overview />
    </BrowserRouter>
  );
}
