import io.shiftleft.semanticcpg.language._
import java.io.PrintWriter

@main def main() = {
  val outJson = sys.env.getOrElse("OUT_JSON", "")
  val extractedRoot = sys.env.getOrElse("EXTRACTED_ROOT", "") // e.g., /home/.../EXTRACTED
  if (outJson.isEmpty || extractedRoot.isEmpty) {
    System.err.println("Missing env vars: OUT_JSON and EXTRACTED_ROOT")
    sys.exit(1)
  }

  def inExtracted(p: String): Boolean =
    p != null && p.nonEmpty && p.startsWith(extractedRoot)

  // Missing calls = calls whose target method is external OR not defined in EXTRACTED
  val missingCalls =
    cpg.call
    .filterNot(_.name.startsWith("<operator>"))
      .flatMap { call =>
        val mf = call.methodFullName
        val targets = cpg.method.fullName(mf).l
        if (targets.isEmpty) {
          List(Map(
            "kind" -> "call",
            "reason" -> "no_method_node",
            "name" -> call.name,
            "code" -> call.code,
            "methodFullName" -> mf,
            "file" -> call.file.name.headOption.getOrElse(""),
            "line" -> call.lineNumber.getOrElse(-1)
          ))
        } else {
          val t = targets.head
          val fileOpt = t.file.name.headOption.getOrElse("")
          val isExternal = t.isExternal
          val isLocal = inExtracted(fileOpt)
          val hasBody = t.ast.size > 0

          if (isExternal || !isLocal || !hasBody) {
            List(Map(
              "kind" -> "call",
              "reason" -> (if (isExternal) "external_method"
                          else if (!isLocal) "defined_outside_extracted"
                          else "no_body"),
              "name" -> call.name,
              "code" -> call.code,
              "methodFullName" -> mf,
              "callFile" -> call.file.name.headOption.getOrElse(""),
              "callLine" -> call.lineNumber.getOrElse(-1),
              "targetFile" -> fileOpt,
              "targetIsExternal" -> isExternal.toString,
              "targetHasBody" -> hasBody.toString
            ))
          } else Nil
        }
      }.l

  // Missing types = typeDecls referenced but defined outside extracted or external
  val missingTypes =
    cpg.typeDecl
      .filter { td =>
        val f = td.file.name.headOption.getOrElse("")
        td.isExternal || !inExtracted(f)
      }
      .map { td =>
        Map(
          "kind" -> "type",
          "reason" -> (if (td.isExternal) "external_type" else "defined_outside_extracted"),
          "name" -> td.name,
          "fullName" -> td.fullName,
          "file" -> td.file.name.headOption.getOrElse("")
        )
      }.l

  val all = missingCalls ++ missingTypes

  def esc(s: String) = s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
  val json = all.map { m =>
    val fields = m.map { case (k, v) =>
      v match {
        case i: Int    => s""""$k": $i"""
        case s: String => s""""$k": "${esc(s)}""""
        case other     => s""""$k": "${esc(other.toString)}""""
      }
    }.mkString(", ")
    s"{$fields}"
  }.mkString("[", ",", "]")

  val pw = new PrintWriter(outJson)
  pw.write(json)
  pw.close()
}
