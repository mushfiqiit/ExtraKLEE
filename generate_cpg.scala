import java.nio.file.{Files, Paths}
import scala.sys.process._

object GenerateLocalCpg {
  def main(args: Array[String]): Unit = {
    val sourceRoot = "/home/mushfiqur/Desktop/Github/ExtraKLEE/EXTRACTED"
    val outputDir = "/home/mushfiqur/Desktop/Github/ExtraKLEE/joern-out"
    val outputFile = s"$outputDir/local.bin"

    val sourcePath = Paths.get(sourceRoot)
    val outputPath = Paths.get(outputDir)

    if (!Files.exists(sourcePath)) {
      Console.err.println(s"Source directory not found: $sourceRoot")
      sys.exit(1)
    }

    if (!Files.exists(outputPath)) {
      Files.createDirectories(outputPath)
      println(s"Created output directory: $outputDir")
    }

    // joern-parse recursively parses all files under the source directory.
    val command = Seq("joern-parse", sourceRoot, "--output", outputFile)

    println("Running command:")
    println(command.mkString(" "))

    val exitCode = command.!

    if (exitCode == 0) {
      println(s"CPG successfully generated at: $outputFile")
    } else {
      Console.err.println(s"Failed to generate CPG. joern-parse exit code: $exitCode")
      sys.exit(exitCode)
    }
  }
}
