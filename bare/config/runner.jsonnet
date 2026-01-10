local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker/build',
  grpcServers: [{
    listenPaths: ['worker/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
