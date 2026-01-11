local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker4/build',
  grpcServers: [{
    listenPaths: ['worker4/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
