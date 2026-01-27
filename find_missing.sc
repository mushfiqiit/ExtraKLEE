import io.shiftleft.semanticcpg.language._
import java.io.PrintWriter
import java.nio.file.{Paths, Files}

@main def main() = {
  val outJson = sys.env.getOrElse("OUT_JSON", "")
  val extractedRoot = sys.env.getOrElse("EXTRACTED_ROOT", "") // e.g., /home/.../EXTRACTED
  if (outJson.isEmpty || extractedRoot.isEmpty) {
    System.err.println("Missing env vars: OUT_JSON and EXTRACTED_ROOT")
    sys.exit(1)
  }

  def inExtracted(p: String): Boolean = {
  if (p == null || p.isEmpty) false
  else Files.exists(Paths.get(extractedRoot).resolve(p))
}

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


val builtins = Set(
  "ANY","void","bool","char","int","size_t","int64_t","nullptr_t","volatile",
  "<global>","main"
)

def isNoiseType(t: String): Boolean =
  t == null || t.isEmpty || builtins.contains(t) || t.startsWith("char[") || t.contains("[")

// 1) Types referenced in code (usage frontier)
val referencedTypes =
  (cpg.identifier.typeFullName.l ++
   cpg.local.typeFullName.l ++
   cpg.parameter.typeFullName.l)
    .distinct
    .filterNot(isNoiseType)

// 2) Types that are actually defined locally inside EXTRACTED
val localTypeDeclFullNames =
  cpg.typeDecl
    .filter(td => inExtracted(td.file.name.headOption.getOrElse("")))
    .fullName
    .toSet

val missingTypeUsages =
  cpg.identifier
    .filter(id => id.typeFullName != null && id.typeFullName.nonEmpty && id.typeFullName != "ANY")
    .filter(id => id.typeFullName.contains("tensorflow") || id.code.contains("TensorShape"))
    .filterNot(id => localTypeDeclFullNames.contains(id.typeFullName))
    .map { id =>
      Map(
        "kind" -> "type",
        "reason" -> "referenced_but_not_defined_locally",
        "name" -> id.typeFullName,
        "code" -> id.code,
        "file" -> id.file.name.headOption.getOrElse(""),
        "line" -> id.lineNumber.getOrElse(-1)
      )
    }.l


  val all = missingCalls ++ missingTypeUsages

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
