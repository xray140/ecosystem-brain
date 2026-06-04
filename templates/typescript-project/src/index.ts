import { greet } from "./core.js";

const name = process.argv[2] ?? "world";
console.log(greet(name));
