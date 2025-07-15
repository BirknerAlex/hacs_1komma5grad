#!/bin/bash

if [ $# -ne 4 ]; then
  echo "Usage: $0 <nextRelease.version> <branch.name> <commits.length> <Date.now()>"
  exit 1
fi

nextReleaseVersion="$1"
branchName="$2"
commitsLength="$3"
timestamp="$4"

mkdir dist

zipCommand="zip ../../dist/einskomma5grad-homeassistant_${nextReleaseVersion}.zip . -r"
echo "Executed command: $zipCommand"

(cd ./custom_components/einskomma5grad && ls -la && $zipCommand)

jsonFile="hacs.json"
if [ -f "$jsonFile" ]; then
  jq ".filename = \"einskomma5grad-homeassistant_${nextReleaseVersion}.zip\"" "$jsonFile" > temp.json
  mv temp.json "$jsonFile"
  echo "Property 'filename' in '$jsonFile' changed to 'einskomma5grad-homeassistant_${nextReleaseVersion}.zip'."
else
  echo "The file '$jsonFile' does not exist."
fi

jsonFile="custom_components/einskomma5grad/manifest.json"
if [ -f "$jsonFile" ]; then
  jq ".version = \"${nextReleaseVersion}\"" "$jsonFile" > temp.json
  mv temp.json "$jsonFile"
  echo "Property 'version' in '$jsonFile' changed to '${nextReleaseVersion}'."
else
  echo "The file '$jsonFile' does not exist."
fi

echo "nextRelease.version: $nextReleaseVersion"
echo "branch.name: $branchName"
echo "commits.length: $commitsLength"
echo "Date.now(): $timestamp"