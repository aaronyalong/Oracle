---
tags: [scala, tools]
---
# sbt

sbt is the standard build tool for Scala.

## build.sbt
```scala
scalaVersion := "3.5.0"
libraryDependencies += "dev.zio" %% "zio" % "2.1.9"
```
`%%` appends the Scala version to the artifact name, so you get the build that matches your compiler.

## Useful commands
- `sbt compile`, `sbt test`, `sbt run`.
- Prefix with `~` to re-run on every file change: `sbt ~test`.
- `sbt console` opens a REPL with your project on the classpath.
