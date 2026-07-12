---
layout: default
title: Hermes Blog
---

# Hermes Blog

全自动内容管线 — 每日发布 AI、科技、金融分析。

## 最新文章

<ul>
{% for post in site.posts limit:10 %}
  <li>
    <a href="{{ post.url }}">{{ post.title }}</a>
    <small>{{ post.date | date: "%Y-%m-%d" }}</small>
  </li>
{% endfor %}
</ul>
