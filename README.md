# Entrofi's `pre-commit` hooks

This setup uses a **versioned hook repository** that works with [pre-commit.com](https://pre-commit.com) and supports *
*multi-module Maven projects**.

## Hooks:

* **Spotless
  **: formats Java code and ensures compliance with Palantir or Google Java Format, running only on files changed vs.
  `HEAD`.
* **Checkstyle**: runs static code analysis on staged `.java` files using your Maven Checkstyle configuration.
* **ADR Scanner**:
  scans architecture decision records in a target directory and creates list of links by extracting first 
  \# Heading from each file; falls back to first non-empty line, then filename stem.
  Replaces content between markers in --target-file.


---

## 🔧 Repository Structure (Hook Repository)

```
java-precommit-hooks/
├─ .pre-commit-hooks.yaml
├─ hooks/
│  ├─ run-spotless.sh
│  └─ run-checkstyle.sh
│  └─ adr-scanner.py
│  └─ ...
└─ README.md  <-- this file
```

---


## 🚀 Usage (Consumer Project)

In your consuming project, create a `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/entrofi/pre-commit-hooks.git
    rev: v0.0.0  
    hooks:
      - id: spotless-java
      - id: checkstyle-java
        args:
          - "--extra-src=src/acceptance,src/integrationTest/java"
      - id: adr-scanner
        args:
          - "--src-dir=docs/architecture/adr"
          - "--target-file=docs/architecture/README.md"
          - "--exclude=archive/**"
          - "--exclude=**/WIP-*.md" 
```

Then install and test the hooks:

```bash
pipx install pre-commit   # or: pip install pre-commit
pre-commit install        # installs the hooks to .git/hooks
pre-commit run --all-files
```

This will:

1. Run **Spotless** (ratchetFrom=HEAD) across changed files and affected modules.
2. Run **Checkstyle** for staged `.java` files in the relevant Maven modules.
3. Run **ADR Scanner** scan `*.md` files under `docs/architecture/adr` and updates the ADR links list in the target file 
`README.md` which is located between the tags `<!--adrlist--> <!--adrliststop-->`

If any hook reformats any file, the commit will fail and the script will restage formatted files for you to re-commit.

---

## 🧩 Multi-Module Support

Both scripts `run-spotless.sh` and `run-checkstyle.sh` automatically discover affected Maven modules:

* For each staged file, they walk up the directory tree to find the nearest `pom.xml`.
* The detected modules are passed to Maven using
  `-pl <modules> -am`, limiting execution to the changed parts of your reactor.

If no `pom.xml` is found, the root project POM is used.

---

## 🏗 Example: Checkstyle Plugin Configuration

Ensure your Maven Checkstyle plugin accepts CLI includes:

```xml

<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-checkstyle-plugin</artifactId>
    <version>${maven-checkstyle-plugin.version}</version>
    <dependencies>
        <dependency>
            <groupId>com.puppycrawl.tools</groupId>
            <artifactId>checkstyle</artifactId>
            <version>${checkstyle.version}</version>
        </dependency>
    </dependencies>
    <configuration>
        <includes>${checkstyle.includes}</includes>
        <failOnViolation>true</failOnViolation>
        <consoleOutput>true</consoleOutput>
        <suppressionsLocation>
            file:${maven.multiModuleProjectDirectory}/config/checkstyle/checkstyle-suppressions.xml
        </suppressionsLocation>
        <configLocation>
            file:${maven.multiModuleProjectDirectory}/config/checkstyle/checkout_checkstyle_10_3_1.xml
        </configLocation>
        <sourceDirectories>
            <sourceDirectory>${project.build.sourceDirectory}</sourceDirectory>
            <sourceDirectory>${project.build.testSourceDirectory}</sourceDirectory>
            <sourceDirectory>${project.basedir}/src/acceptance</sourceDirectory>
        </sourceDirectories>
    </configuration>
</plugin>
```

---

## 💅 Example: Spotless Plugin Configuration

Spotless plugin in `pom.xml`:

```xml

<properties>
    <spotless.ratchetFrom>origin/main</spotless.ratchetFrom>
</properties>

<plugin>
<groupId>com.diffplug.spotless</groupId>
<artifactId>spotless-maven-plugin</artifactId>
<version>2.46.1</version>
<configuration>
    <ratchetFrom>${spotless.ratchetFrom}</ratchetFrom>
    <java>
        <palantirJavaFormat/>
        <removeUnusedImports/>
        <importOrder/>
    </java>
</configuration>
</plugin>
```

---

## 🧩 Example Workflow

```bash
# Developer clones project
pipx install pre-commit
pre-commit install

# Developer makes changes and stages files
git add .

# On git commit:
# 1. Spotless ensures formatting (ratchetFrom=HEAD)
# 2. Checkstyle analyzes staged files
# 3. If all checks pass, commit proceeds
```

