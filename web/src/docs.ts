// the docs page: smooth scrolling, and the contents list follows the section being read
import { startScroll } from "./scroll.js";

function followSections(): (scroll: number) => void {
  const links = Array.from(document.querySelectorAll<HTMLAnchorElement>(".toc a"));
  const heads = links
    .map((link) => document.querySelector<HTMLElement>(link.getAttribute("href") ?? ""))
    .filter((head): head is HTMLElement => head !== null);
  let current = -1;
  return (scroll: number) => {
    const line = scroll + window.innerHeight * 0.3;
    let index = 0;
    heads.forEach((head, i) => {
      if (head.offsetTop <= line) index = i;
    });
    if (index === current) return;
    current = index;
    links.forEach((link, i) => link.classList.toggle("on", i === index));
  };
}

startScroll([followSections()]);
