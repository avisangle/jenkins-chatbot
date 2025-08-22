#!/usr/bin/env groovy

/*
 * This Jenkinsfile is intended to run on https://ci.jenkins.io and may fail anywhere else.
 * It makes assumptions about plugins being installed, labels mapping to nodes that can build what is needed, etc.
 */

buildPlugin(
    useContainerAgent: true, // Set to `false` if you need to use Docker for containerized tests
    configurations: [
        [platform: 'linux', jdk: 21],
        [platform: 'windows', jdk: 17],
    ]
)