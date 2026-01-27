import io.shiftleft.semanticcpg.language._

@main def main() = {
  val cpgPath = sys.env.getOrElse("CPG_PATH", "")
  val extractedRoot = sys.env.getOrElse("EXTRACTED_ROOT", "")
  if (cpgPath.isEmpty || extractedRoot.isEmpty) {
    System.err.println("Missing env vars: CPG_PATH and EXTRACTED_ROOT")
    sys.exit(1)
  }

  // Load the CPG explicitly (works even when joern CLI flags differ)
  importCpg(cpgPath)

  def inExtracted(p: String): Boolean =
    p != null && p.nonEmpty && p.startsWith(extractedRoot)

  // 1) Verify the header is actually in the CPG
  println("=== Files matching tensor_shape.h ===")
  println(cpg.file.name(".*tensor_shape\\.h").name.l.mkString("\n"))

  // 2) Show typeDecls named TensorShape + where they are defined
  println("\n=== typeDecl TensorShape candidates ===")
  val tds = cpg.typeDecl.name("TensorShape")
    .map(td => (td.fullName, td.file.name.headOption.getOrElse(""), td.isExternal))
    .l
  tds.foreach(println)

  // 3) Show identifier typeFullNames that mention TensorShape
  println("\n=== identifier usages mentioning TensorShape ===")
  val ids = cpg.identifier
    .filter(id => Option(id.typeFullName).getOrElse("").contains("TensorShape") || Option(id.code).getOrElse("").contains("tensor_shape"))
    .map(id => (id.code, id.typeFullName, id.file.name.headOption.getOrElse(""), id.lineNumber.getOrElse(-1)))
    .l
  ids.foreach(println)

  // 4) Check whether TensorShape is local (defined under EXTRACTED_ROOT)
  println("\n=== TensorShape defined in EXTRACTED_ROOT? ===")
  val localTensorShape = cpg.typeDecl.name("TensorShape")
    .filter(td => inExtracted(td.file.name.headOption.getOrElse("")))
    .map(td => (td.fullName, td.file.name.headOption.getOrElse("")))
    .l
  if (localTensorShape.isEmpty) println("NO local TensorShape typeDecl under EXTRACTED_ROOT")
  else localTensorShape.foreach(println)
}
