All your chat history pages are listed below:

```query
page
where name =~ "^chat_history/" select name,size
render [[template/link]]
```