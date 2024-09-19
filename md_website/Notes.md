All your note pages are listed below:

```query
page
where name =~ "^notes/" select name,size
render [[template/link]]
```