import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props { rotulo?: string; children: ReactNode }
interface State { falhou: boolean }

/** Isola falha de renderização de um painel: o restante da página continua utilizável. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { falhou: false };

  static getDerivedStateFromError(): State { return { falhou: true }; }

  componentDidCatch(_erro: Error, _info: ErrorInfo): void {
    // Sem log do conteúdo: a mensagem pode conter dado do estudo.
  }

  render(): ReactNode {
    if (!this.state.falhou) return this.props.children;
    return (
      <div className="card error" role="alert">
        Não foi possível exibir {this.props.rotulo ?? "este painel"}. Reanalise o estudo ou recarregue a página.
      </div>
    );
  }
}
